/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 * 
 * Logging Utility for Security Lake Integration Framework
 * 
 * Provides structured logging for CDK synthesis and deployment.
 */

export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3
}

export interface LogContext {
  [key: string]: any;
}

/**
 * Logger class for structured logging
 */
export class Logger {
  private readonly component: string;
  private readonly minLevel: LogLevel;

  constructor(component: string, minLevel: LogLevel = LogLevel.INFO) {
    this.component = component;
    this.minLevel = minLevel;
  }

  /**
   * Log debug message
   */
  debug(message: string, context?: LogContext): void {
    if (this.minLevel <= LogLevel.DEBUG) {
      this.log('DEBUG', message, context);
    }
  }

  /**
   * Log info message
   */
  info(message: string, context?: LogContext): void {
    if (this.minLevel <= LogLevel.INFO) {
      this.log('INFO', message, context);
    }
  }

  /**
   * Log warning message
   */
  warn(message: string, context?: LogContext): void {
    if (this.minLevel <= LogLevel.WARN) {
      this.log('WARN', message, context);
    }
  }

  /**
   * Log error message
   */
  error(message: string, error?: Error | any, context?: LogContext): void {
    if (this.minLevel <= LogLevel.ERROR) {
      const errorContext = {
        ...context,
        ...(error instanceof Error ? {
          errorMessage: error.message,
          errorStack: error.stack
        } : {
          error: String(error)
        })
      };
      this.log('ERROR', message, errorContext);
    }
  }

  /**
   * Internal log method
   */
  private log(level: string, message: string, context?: LogContext): void {
    const timestamp = new Date().toISOString();
    const logEntry: any = {
      timestamp,
      level,
      component: this.component,
      message
    };

    if (context && Object.keys(context).length > 0) {
      logEntry.context = context;
    }

    console.log(JSON.stringify(logEntry));
  }
}