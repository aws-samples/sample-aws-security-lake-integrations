/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 *
 * Template validation wrapper for CDK integration.
 * Invokes the Python template validator as a subprocess and parses results.
 */

import { spawnSync, SpawnSyncReturns } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

export interface ValidationError {
  phase: string;
  severity: string;
  message: string;
  template_file: string;
  line_number?: number;
  column_number?: number;
  field_path?: string;
  suggestion?: string;
}

export interface TemplateValidationResult {
  template_file: string;
  is_valid: boolean;
  error_count: number;
  warning_count: number;
  errors: ValidationError[];
  warnings: ValidationError[];
}

export interface AggregatedValidationResult {
  summary: {
    total_templates: number;
    valid_templates: number;
    invalid_templates: number;
    total_errors: number;
    total_warnings: number;
    all_valid: boolean;
  };
  templates: TemplateValidationResult[];
}

export class TemplateValidationError extends Error {
  constructor(
    message: string,
    public readonly results: AggregatedValidationResult
  ) {
    super(message);
    this.name = 'TemplateValidationError';
  }
}

export interface ValidateTemplatesOptions {
  warningsAsErrors?: boolean;
  singleTemplate?: string;
  pythonPath?: string;
  strict?: boolean;
}

/**
 * Validates templates by invoking the Python validator subprocess.
 * Returns the parsed validation results.
 */
export function validateTemplates(
  templatesDir: string,
  options: ValidateTemplatesOptions = {}
): AggregatedValidationResult {
  const pythonPath = options.pythonPath || 'python3';

  // Path to the validation CLI module
  const validatorModule = path.join(
    __dirname,
    '..',
    '..',
    'src',
    'lambda',
    'event-transformer',
    'validation'
  );

  // Check if validator exists
  const cliPath = path.join(validatorModule, 'cli.py');
  if (!fs.existsSync(cliPath)) {
    throw new Error(
      `Template validator not found at: ${cliPath}. ` +
        `Ensure the validation package is installed.`
    );
  }

  // Build command arguments
  const args = [
    '-m',
    'validation.cli',
    '--templates-dir',
    templatesDir,
    '--output-format',
    'json',
    '--no-color',
  ];

  if (options.singleTemplate) {
    args.push('--template', options.singleTemplate);
  }

  if (options.warningsAsErrors) {
    args.push('--warnings-as-errors');
  }

  if (options.strict === false) {
    args.push('--no-strict');
  }

  // Execute Python validator
  // Set working directory to event-transformer so Python can find the module
  const workingDir = path.join(
    __dirname,
    '..',
    '..',
    'src',
    'lambda',
    'event-transformer'
  );

  const result: SpawnSyncReturns<string> = spawnSync(pythonPath, args, {
    encoding: 'utf-8',
    maxBuffer: 10 * 1024 * 1024, // 10MB buffer for large outputs
    cwd: workingDir,
  });

  // Check for execution errors
  if (result.error) {
    throw new Error(
      `Failed to execute template validator: ${result.error.message}`
    );
  }

  // Parse JSON output
  let validationResult: AggregatedValidationResult;
  try {
    if (!result.stdout || result.stdout.trim() === '') {
      throw new Error('Empty output from validator');
    }
    validationResult = JSON.parse(result.stdout);
  } catch (e) {
    const errorMsg = e instanceof Error ? e.message : String(e);
    throw new Error(
      `Failed to parse validation output: ${errorMsg}\n` +
        `stdout: ${result.stdout}\n` +
        `stderr: ${result.stderr}`
    );
  }

  return validationResult;
}

/**
 * Validates templates and throws an error if validation fails.
 * This is the main function to use in CDK synth hooks.
 */
export function validateTemplatesOrThrow(
  templatesDir: string,
  options: ValidateTemplatesOptions = {}
): void {
  const result = validateTemplates(templatesDir, options);

  if (!result.summary.all_valid) {
    // Format error message for console output
    let message = `Template validation failed: ${result.summary.invalid_templates} template(s) have errors\n`;
    message += `Total errors: ${result.summary.total_errors}\n\n`;

    for (const template of result.templates) {
      if (template.errors.length > 0) {
        // Extract just the filename for cleaner output
        const filename = path.basename(template.template_file);
        message += `${filename}:\n`;

        for (const error of template.errors) {
          const location = error.line_number
            ? `:${error.line_number}${error.column_number ? ':' + error.column_number : ''}`
            : '';
          message += `  [${error.phase}] Line${location}\n`;
          message += `    ${error.message}\n`;
          if (error.field_path) {
            message += `    Field: ${error.field_path}\n`;
          }
          if (error.suggestion) {
            message += `    Suggestion: ${error.suggestion}\n`;
          }
        }
        message += '\n';
      }
    }

    throw new TemplateValidationError(message, result);
  }

  // Log warnings if any
  if (result.summary.total_warnings > 0) {
    console.warn(
      `Template validation passed with ${result.summary.total_warnings} warning(s)`
    );
    for (const template of result.templates) {
      for (const warning of template.warnings) {
        const filename = path.basename(template.template_file);
        console.warn(`  [WARNING] ${filename}: ${warning.message}`);
      }
    }
  }
}

/**
 * Gets the default templates directory path.
 */
export function getDefaultTemplatesDir(): string {
  return path.join(
    __dirname,
    '..',
    '..',
    'src',
    'lambda',
    'event-transformer',
    'templates'
  );
}