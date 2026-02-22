import { defineVitestConfig } from '@nuxt/test-utils/config'

export default defineVitestConfig({
    test: {
        environment: 'nuxt',
        globals: true,
        hookTimeout: 60000,
        testTimeout: 60000,
        exclude: ['**/node_modules/**', '**/dist/**', '**/.{idea,git,cache,output,temp}/**', '**/tests/e2e/**', '**/*.e2e.spec.ts', '**/e2e.spec.ts'],
    }
})
