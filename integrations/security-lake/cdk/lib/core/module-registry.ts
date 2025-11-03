/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 * 
 * Module Registry for Security Lake Integration Framework
 * 
 * Central registry for all available integration modules.
 * Provides static registration of modules to avoid dynamic import complexity.
 */

import { IIntegrationModule } from './integration-module-interface';
import { Logger } from './logger';

const logger = new Logger('ModuleRegistry');

/**
 * Module factory function type
 */
export type ModuleFactory = () => IIntegrationModule;

/**
 * Module registry stores available integration modules
 */
class ModuleRegistryClass {
  private readonly modules: Map<string, ModuleFactory> = new Map();

  /**
   * Register an integration module
   * 
   * @param moduleId - Unique module identifier
   * @param factory - Factory function that creates module instance
   */
  register(moduleId: string, factory: ModuleFactory): void {
    if (this.modules.has(moduleId)) {
      logger.warn(`Module ${moduleId} is already registered, overwriting`);
    }

    this.modules.set(moduleId, factory);
    logger.info(`Registered module: ${moduleId}`);
  }

  /**
   * Get a module by ID
   * 
   * @param moduleId - Module identifier
   * @returns Module instance or undefined if not found
   */
  getModule(moduleId: string): IIntegrationModule | undefined {
    const factory = this.modules.get(moduleId);
    if (!factory) {
      logger.warn(`Module ${moduleId} not found in registry`);
      return undefined;
    }

    try {
      const module = factory();
      logger.debug(`Created instance of module: ${moduleId}`);
      return module;
    } catch (error) {
      logger.error(`Failed to create module instance: ${moduleId}`, error);
      throw error;
    }
  }

  /**
   * Check if module is registered
   * 
   * @param moduleId - Module identifier
   * @returns true if module is registered
   */
  hasModule(moduleId: string): boolean {
    return this.modules.has(moduleId);
  }

  /**
   * Get all registered module IDs
   * 
   * @returns Array of module IDs
   */
  getRegisteredModuleIds(): string[] {
    return Array.from(this.modules.keys());
  }

  /**
   * Get count of registered modules
   * 
   * @returns Number of registered modules
   */
  getModuleCount(): number {
    return this.modules.size;
  }

  /**
   * Unregister a module
   * 
   * @param moduleId - Module identifier
   * @returns true if module was unregistered
   */
  unregister(moduleId: string): boolean {
    const result = this.modules.delete(moduleId);
    if (result) {
      logger.info(`Unregistered module: ${moduleId}`);
    }
    return result;
  }

  /**
   * Clear all registered modules
   * Primarily for testing purposes
   */
  clear(): void {
    this.modules.clear();
    logger.info('Module registry cleared');
  }
}

/**
 * Singleton instance of module registry
 */
export const ModuleRegistry = new ModuleRegistryClass();

/**
 * Decorator for auto-registering modules
 * 
 * @example
 * ```typescript
 * @RegisterModule('azure')
 * export class AzureIntegrationModule extends BaseIntegrationModule {
 *   // ...
 * }
 * ```
 */
export function RegisterModule(moduleId: string) {
  return function <T extends { new(...args: any[]): IIntegrationModule }>(constructor: T) {
    ModuleRegistry.register(moduleId, () => new constructor());
    return constructor;
  };
}

/**
 * Helper function to register module manually
 * 
 * @param moduleId - Module identifier
 * @param moduleClass - Module class constructor
 */
export function registerModule<T extends { new(): IIntegrationModule }>(
  moduleId: string,
  moduleClass: T
): void {
  ModuleRegistry.register(moduleId, () => new moduleClass());
}