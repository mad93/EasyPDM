import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import { runInThisContext } from "node:vm"
import test from "node:test"
import ts from "typescript"

// Load just the dictionaries without Vite, React, or a browser. The build also
// type-checks them; these tests check runtime keys and interpolation parameters.
function loadDictionary(name) {
  const filename = fileURLToPath(new URL(`../src/i18n/${name}.ts`, import.meta.url))
  const { outputText } = ts.transpileModule(readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  })
  const module = { exports: {} }
  const execute = runInThisContext(`(function(require, module, exports) {${outputText}\n})`, { filename })
  execute((path) => {
    assert.equal(path, "./translations-ca-es")
    return loadDictionary("translations-ca-es")
  }, module, module.exports)
  return module.exports
}

const { translations, LANGUAGE_NATIVE_NAMES } = loadDictionary("translations")
const parameters = (text) => [...text.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/g)]
  .map((match) => match[1]).sort()

for (const language of ["ca", "es"]) {
  test(`${language}: all keys are translated and all parameters are preserved`, () => {
    assert.deepEqual(Object.keys(translations[language]).sort(), Object.keys(translations.en).sort())
    for (const [key, value] of Object.entries(translations[language])) {
      assert.equal(typeof value, "string", key)
      assert.ok(value.trim().length > 0, key)
      assert.deepEqual(parameters(value), parameters(translations.en[key]), `${language}: ${key}`)
    }
  })
}

test("the selector includes all five languages with their native names", () => {
  assert.deepEqual(Object.keys(LANGUAGE_NATIVE_NAMES).sort(), ["ca", "de", "en", "es", "pl"])
  assert.equal(LANGUAGE_NATIVE_NAMES.ca, "Català")
  assert.equal(LANGUAGE_NATIVE_NAMES.es, "Castellano")
})

test("representative interface strings use the requested languages", () => {
  assert.equal(translations.ca["settings.language"], "Idioma")
  assert.equal(translations.ca["itemType.part"], "Peça")
  assert.equal(translations.es["itemType.part"], "Pieza")
  assert.equal(translations.ca["transfer.counter"].replace("{done}", "2").replace("{total}", "5"), "2 de 5")
  assert.notEqual(translations.ca["storage.clearDatabasePhrase"], translations.es["storage.clearDatabasePhrase"])
})
