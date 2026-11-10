import { describe, expect, it } from 'vitest'
import type {
  GpsSample,
  RecordedRoute,
} from './gpsTypes'
import {
  calculateDistanceMeters,
  calculateRouteDistanceMeters,
  createRouteSummary,
  isSampleAccurate,
} from './routeMetrics'

function createSample(
  overrides: Partial<GpsSample> = {},
): GpsSample {
  return {
    latitude: 34.6901,
    longitude: 135.1955,
    accuracyMeters: 10,
    timestampMs: 1_700_000_000_000,
    ...overrides,
  }
}

describe('routeMetrics', () => {
  it('同じ座標間の距離は0になる', () => {
    const sample = createSample()

    expect(calculateDistanceMeters(sample, sample)).toBe(0)
  })

  it('異なる2地点間の距離を計算する', () => {
    const start = createSample({
      latitude: 34.6901,
      longitude: 135.1955,
    })
    const end = createSample({
      latitude: 34.691,
      longitude: 135.1955,
    })

    const distance = calculateDistanceMeters(start, end)

    expect(distance).toBeGreaterThan(90)
    expect(distance).toBeLessThan(110)
  })

  it('50メートル以内の精度を有効として扱う', () => {
    expect(
      isSampleAccurate(
        createSample({ accuracyMeters: 50 }),
      ),
    ).toBe(true)
  })

  it('50メートルを超える精度を無効として扱う', () => {
    expect(
      isSampleAccurate(
        createSample({ accuracyMeters: 51 }),
      ),
    ).toBe(false)
  })

  it('精度が悪い地点を距離計算から除外する', () => {
    const samples = [
      createSample({
        latitude: 34.6901,
        accuracyMeters: 10,
      }),
      createSample({
        latitude: 35,
        accuracyMeters: 100,
      }),
      createSample({
        latitude: 34.691,
        accuracyMeters: 10,
      }),
    ]

    const distance = calculateRouteDistanceMeters(samples)

    expect(distance).toBeGreaterThan(90)
    expect(distance).toBeLessThan(110)
  })

  it('ルート概要を作成する', () => {
    const route: RecordedRoute = {
      id: 'test-route',
      startedAtMs: 1_000,
      endedAtMs: 11_000,
      samples: [
        createSample({
          latitude: 34.6901,
          accuracyMeters: 10,
        }),
        createSample({
          latitude: 34.691,
          accuracyMeters: 10,
        }),
        createSample({
          latitude: 34.692,
          accuracyMeters: 80,
        }),
      ],
      stopReason: 'user',
    }

    const summary = createRouteSummary(route)

    expect(summary.elapsedMs).toBe(10_000)
    expect(summary.acceptedSampleCount).toBe(2)
    expect(summary.rejectedSampleCount).toBe(1)
    expect(summary.distanceMeters).toBeGreaterThan(90)
    expect(summary.distanceMeters).toBeLessThan(110)
  })
})