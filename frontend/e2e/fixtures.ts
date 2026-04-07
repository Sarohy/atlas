import { test as base } from '@playwright/test';

// Extend base test with shared fixtures as needed for future tests.
export const test = base;
export { expect } from '@playwright/test';
