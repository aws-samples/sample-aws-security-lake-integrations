/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 * 
 * Module Loader for Security Lake Integration Framework
 * 
 * Dynamically loads and manages integration modules based on configuration.
 * Handles module validation, registration, and lifecycle management.
 */

import { Construct } from 'constructs';
import { IIntegrationModule, CoreResources, ValidationResult } from './integration-module-interface';
import { Logger } from './logger';
import { ModuleRegistry } from './module-registry';

/**
 * Module loader configuration
 */
export interface ModuleLoaderConfig {
  /** Base path for module resolution */
  modulesBasePath?: string;
  
  /** Whether to fail fast on module errors */
  strictMode?: boolean;
}

/**
 * Loaded module information
 */
export interface LoadedModule {
  /** Module instance */
  module: IIntegrationModule;
  
  /** Module configuration */
  config: any;
  
  /** Validation result */
  validation: ValidationResult;
  
  /** Whether module is enabled */
  enabled: boolean;
}

/**
 * ModuleLoader manages dynamic loading and registration of integration modules
 */
export class ModuleLoader {
  private readonly logger: Logger;
  private readonly config: ModuleLoaderConfig;
  private readonly loadedModules: Map<string, LoadedModule> = new Map();

  constructor(config: ModuleLoaderConfig = {}) {
    this.logger = new Logger('ModuleLoader');
    this.config = {
      modulesBasePath: config.modulesBasePath || '../modules',
      strictMode: config.strictMode !== false // Default to true
    };
  }

  /**
   * Load integration modules from configuration
   * 
   * @param integrationsConfig - Configuration object with integration definitions
   * @returns Array of loaded modules
   */
  async loadModules(integrationsConfig: any): Promise<LoadedModule[]> {
    this.logger.info('Loading integration modules', {
      configuredModules: Object.keys(integrationsConfig || {})
    });

    if (!integrationsConfig) {
      this.logger.warn('No integrations configured');
      return [];
    }

    const modules: LoadedModule[] = [];

    for (const [moduleId, moduleConfig] of Object.entries(integrationsConfig)) {
      try {
        const loadedModule = await this.loadModule(moduleId, moduleConfig as any);
        if (loadedModule) {
          modules.push(loadedModule);
          this.loadedModules.set(moduleId, loadedModule);
        }
      } catch (error) {
        const errorMsg = `Failed to load module ${moduleId}`;
        this.logger.error(errorMsg, error);
        
        if (this.config.strictMode) {
          throw new Error(`${errorMsg}: ${error instanceof Error ? error.message : String(error)}`);
        }
      }
    }

    this.logger.info('Module loading complete', {
      totalModules: modules.length,
      enabledModules: modules.filter(m => m.enabled).length
    });

    return modules;
  }

  /**
   * Load a single integration module
   * 
   * @param moduleId - Unique module identifier
   * @param moduleConfig - Module configuration
   * @returns LoadedModule or undefined if disabled
   */
  private async loadModule(moduleId: string, moduleConfig: any): Promise<LoadedModule | undefined> {
    this.logger.info(`Loading module: ${moduleId}`, { enabled: moduleConfig.enabled });

    // Skip if module is disabled
    if (moduleConfig.enabled === false) {
      this.logger.info(`Module ${moduleId} is disabled, skipping`);
      return undefined;
    }

    // Dynamically import module based on modulePath or convention
    const modulePath = moduleConfig.modulePath || `modules/${moduleId}`;
    
    this.logger.debug(`Attempting to import module from: ${modulePath}`);

    let moduleClass: IIntegrationModule;
    try {
      // Try to import the module
      // In a real implementation, this would use dynamic imports
      // For now, we'll use the module registry approach
      const moduleInstance = await this.importModule(modulePath, moduleId);
      moduleClass = moduleInstance;
    } catch (error) {
      throw new Error(`Failed to import module ${moduleId} from ${modulePath}: ${error}`);
    }

    // Validate module instance
    this.validateModuleInstance(moduleClass);

    // Validate module configuration
    const validation = moduleClass.validateConfig(moduleConfig.config || {});

    if (!validation.valid) {
      const errorMsg = `Module ${moduleId} configuration validation failed`;
      this.logger.error(errorMsg, null, {
        errors: validation.errors,
        warnings: validation.warnings
      });

      if (this.config.strictMode) {
        throw new Error(`${errorMsg}: ${validation.errors?.join(', ')}`);
      }
    }

    // Log warnings even if validation passed
    if (validation.warnings && validation.warnings.length > 0) {
      this.logger.warn(`Module ${moduleId} has configuration warnings`, {
        warnings: validation.warnings
      });
    }

    this.logger.info(`Module ${moduleId} loaded successfully`, {
      version: moduleClass.moduleVersion,
      hasConfig: !!moduleConfig.config
    });

    return {
      module: moduleClass,
      config: moduleConfig.config || {},
      validation,
      enabled: true
    };
  }

  /**
   * Import module from registry
   *
   * Modules must be pre-registered in the ModuleRegistry before loading.
   * This avoids dynamic import complexity in CDK context.
   *
   * @param modulePath - Path to module (unused, kept for interface compatibility)
   * @param moduleId - Module identifier
   * @returns Module instance
   */
  private async importModule(modulePath: string, moduleId: string): Promise<IIntegrationModule> {
    // Get module from registry
    const module = ModuleRegistry.getModule(moduleId);
    
    if (!module) {
      throw new Error(
        `Module '${moduleId}' not found in registry. ` +
        `Available modules: ${ModuleRegistry.getRegisteredModuleIds().join(', ') || 'none'}. ` +
        `Ensure the module is registered in the CDK app entry point.`
      );
    }
    
    return module;
  }

  /**
   * Validate that module instance implements required interface
   * 
   * @param module - Module instance to validate
   * @throws Error if module doesn't implement required methods
   */
  private validateModuleInstance(module: IIntegrationModule): void {
    const requiredProperties = ['moduleId', 'moduleName', 'moduleVersion', 'moduleDescription'];
    const requiredMethods = ['validateConfig', 'createResources', 'getRequiredPermissions'];

    // Check required properties
    for (const prop of requiredProperties) {
      if (!(prop in module)) {
        throw new Error(`Module missing required property: ${prop}`);
      }
    }

    // Check required methods
    for (const method of requiredMethods) {
      if (typeof (module as any)[method] !== 'function') {
        throw new Error(`Module missing required method: ${method}`);
      }
    }

    // Validate version format
    const semverRegex = /^\d+\.\d+\.\d+$/;
    if (!semverRegex.test(module.moduleVersion)) {
      throw new Error(`Invalid module version format: ${module.moduleVersion}. Must be semver (x.y.z)`);
    }

    // Validate module ID format
    const idRegex = /^[a-z][a-z0-9-]*$/;
    if (!idRegex.test(module.moduleId)) {
      throw new Error(`Invalid module ID format: ${module.moduleId}. Must be lowercase alphanumeric with hyphens`);
    }
  }

  /**
   * Initialize loaded modules in the CDK stack
   * 
   * @param scope - CDK construct scope
   * @param coreResources - Core resources to pass to modules
   */
  initializeModules(scope: Construct, coreResources: CoreResources): void {
    this.logger.info('Initializing modules', {
      totalModules: this.loadedModules.size
    });

    for (const [moduleId, loadedModule] of this.loadedModules.entries()) {
      if (!loadedModule.enabled) {
        continue;
      }

      try {
        this.logger.info(`Initializing module: ${moduleId}`);
        
        // Create module resources
        loadedModule.module.createResources(scope, coreResources, loadedModule.config);
        
        this.logger.info(`Module ${moduleId} initialized successfully`);
      } catch (error) {
        const errorMsg = `Failed to initialize module ${moduleId}`;
        this.logger.error(errorMsg, error);
        
        if (this.config.strictMode) {
          throw new Error(`${errorMsg}: ${error instanceof Error ? error.message : String(error)}`);
        }
      }
    }

    this.logger.info('All modules initialized successfully');
  }

  /**
   * Get loaded modules
   * 
   * @returns Map of module IDs to loaded modules
   */
  getLoadedModules(): Map<string, LoadedModule> {
    return this.loadedModules;
  }

  /**
   * Get a specific loaded module
   * 
   * @param moduleId - Module identifier
   * @returns LoadedModule or undefined
   */
  getModule(moduleId: string): LoadedModule | undefined {
    return this.loadedModules.get(moduleId);
  }

  /**
   * Get all enabled modules
   * 
   * @returns Array of enabled modules
   */
  getEnabledModules(): LoadedModule[] {
    return Array.from(this.loadedModules.values()).filter(m => m.enabled);
  }
}