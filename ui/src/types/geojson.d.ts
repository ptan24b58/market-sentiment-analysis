// Module declaration so TypeScript accepts *.geojson imports/requires.
declare module '*.geojson' {
  import type { FeatureCollection } from 'geojson'
  const value: FeatureCollection
  export default value
}
