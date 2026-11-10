import type {
  FeatureCollection,
  LineString,
  MultiPolygon,
  Polygon,
} from 'geojson'
import type { GpsSample } from '../recording/gpsTypes'
import type { RouteLineProperties } from '../recording/routeGeoJson'

export type TerritoryProperties = {
  id: string
  label?: string
  ownerId?: string
  fillColor?: string
  outlineColor?: string
}

export type RouteFeatureCollection = FeatureCollection<
  LineString,
  RouteLineProperties
>

export type TerritoryFeatureCollection = FeatureCollection<
  Polygon | MultiPolygon,
  TerritoryProperties
>

export type MapViewProps = {
  center?: readonly [
    longitude: number,
    latitude: number,
  ]
  zoom?: number
  routeLines?: RouteFeatureCollection
  territories?: TerritoryFeatureCollection
  activePosition?: GpsSample | null
  className?: string
  onMapReady?: () => void
  onMapError?: (error: Error) => void
}