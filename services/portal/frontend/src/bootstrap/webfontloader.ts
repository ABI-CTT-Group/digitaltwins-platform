/**
 * plugins/webfontloader.ts
 *
 * webfontloader documentation: https://github.com/typekit/webfontloader
 */

export async function loadFonts () {
  const webFontLoader = await import(/* webpackChunkName: "webfontloader" */'webfontloader')

  webFontLoader.load({
    google: {
      // families: ['Nunito:100,300,400,500,700,900&display=swap'],
      families: ['Nunito:200,300,400,500,600,700,800,900', 'Nunito:200italic,300italic,400italic,500italic,600italic,700italic,800italic,900italic']
    },
  })
}
