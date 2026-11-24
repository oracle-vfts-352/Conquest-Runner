import type {
  Feature,
  FeatureCollection,
  LineString,
} from 'geojson'
import type { RecordedRoute } from './gpsTypes'

export type RouteLineStatus =
  | 'recording'
  | 'preview'
  | 'submitted'

export type RouteLineProperties = {
  id: string
  status: RouteLineStatus
  startedAtMs: number
  endedAtMs: number | null
}

export type RouteLineFeature = Feature<
  LineString,
  RouteLineProperties
>

export function routeToLineFeature(
  route: RecordedRoute,
  status: RouteLineStatus = 'preview',
): RouteLineFeature {
  return {
    type: 'Feature',
    properties: {
      id: route.id,
      status,
      startedAtMs: route.startedAtMs,
      endedAtMs: route.endedAtMs,
    },
    geometry: {
      type: 'LineString',
      coordinates: route.samples.map((sample) => [
        sample.longitude,
        sample.latitude,
      ]),
    },
  }
}

export function routesToFeatureCollection(
  routes: RecordedRoute[],
  status: RouteLineStatus = 'preview',
): FeatureCollection<
  LineString,
  RouteLineProperties
> {
  return {
    type: 'FeatureCollection',
    features: routes.map((route) =>
      routeToLineFeature(route, status),
    ),
  }
}