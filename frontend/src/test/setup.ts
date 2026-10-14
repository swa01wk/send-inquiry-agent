import '@testing-library/jest-dom/vitest'

if (typeof Element.prototype.scrollIntoView !== 'function') {
  Element.prototype.scrollIntoView = () => undefined
}
