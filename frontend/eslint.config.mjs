import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)

/** @type {import('eslint').Linter.Config[]} */
const nextConfig = require('eslint-config-next')

export default nextConfig
