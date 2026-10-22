import js from '@eslint/js';
import ts from 'typescript-eslint';
export default ts.config({ignores:['dist/**','dist-dev/**','node_modules/**','artifacts/**','test-results/**','playwright-report/**']}, js.configs.recommended, ...ts.configs.recommended, {files:['scripts/*.mjs'],languageOptions:{globals:{process:'readonly',console:'readonly',Buffer:'readonly',fetch:'readonly',AbortSignal:'readonly'}}});
