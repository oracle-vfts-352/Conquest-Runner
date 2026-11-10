import { describe, expect, it } from 'vitest'
import type { RecordedRoute } from './gpsTypes'
import {
  routeToLineFeature,
  routesToFeatureCollection,
} from './routeGeoJson'

function createRoute(): RecordedRoute {
  return {
    id: 'route-1',
    startedAtMs: 1_000,
    endedAtMs: 11_000,
    stopReason: 'user',
    samples: [
      {
        latitude: 34.6901,
        longitude: 135.1955,
        accuracyMeters: 10,
        timestampMs: 1_000,
      },
      {
        latitude: 34.691,
        longitude: 135.196,
        accuracyMeters: 12,
        timestampMs: 2_000,
      },
    ],
  }
}

describe('routeGeoJson', () => {
  it('GPSルートをGeoJSON LineStringへ変換する', () => {
    const feature = routeToLineFeature(createRoute())

    expect(feature.type).toBe('Feature')
    expect(feature.geometry.type).toBe('LineString')
    expect(feature.properties.id).toBe('route-1')
    expect(feature.properties.status).toBe('preview')
  })

  it('座標を経度、緯度の順で出力する', () => {
    const feature = routeToLineFeature(createRoute())

    expect(feature.geometry.coordinates).toEqual([
      [135.1955, 34.6901],
      [135.196, 34.691],
    ])
  })

  it('指定されたルート状態を保持する', () => {
    const feature = routeToLineFeature(
      createRoute(),
      'recording',
    )

    expect(feature.properties.status).toBe('recording')
  })

  it('複数ルートをFeatureCollectionへ変換する', () => {
    const collection = routesToFeatureCollection([
      createRoute(),
    ])

    expect(collection.type).toBe('FeatureCollection')
    expect(collection.features).toHaveLength(1)
    expect(
      collection.features[0].properties.id,
    ).toBe('route-1')
  })

  it('空配列から空のFeatureCollectionを作る', () => {
    const collection = routesToFeatureCollection([])

    expect(collection.features).toEqual([])
  })
})