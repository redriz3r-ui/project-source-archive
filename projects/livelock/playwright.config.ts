import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'tests/e2e',workers:1,timeout:60000,reporter:[['list'],['json',{outputFile:'artifacts/e2e-results.json'}]]});
