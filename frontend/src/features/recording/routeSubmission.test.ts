import { describe, expect, it } from 'vitest'
import type { RecordedRoute } from './gpsTypes'
import {
  createRouteSubmissionPayload,
  IncompleteRouteError,
} from './routeSubmission'

function createStoppedRoute(): RecordedRoute {
  return {
    id: 'route-1',
    startedAtMs: Date.UTC(2026, 10, 10, 1, 0, 0),
    endedAtMs: Date.UTC(2026, 10, 10, 1, 10, 0),
    stopReason: 'user',
    samples: [
      {
        latitude: 34.6901,
        longitude: 135.1955,
        accuracyMeters: 10,
        timestampMs: Date.UTC(2026, 10, 10, 1, 0, 1),
        altitudeMeters: 18.2,
        altitudeAccuracyMeters: 4,
        headingDegrees: 90,
        speedMetersPerSecond: 2.4,
      },
      {
        latitude: 34.691,
        longitude: 135.1955,
        accuracyMeters: 12,
        timestampMs: Date.UTC(2026, 10, 10, 1, 1, 0),
      },
    ],
  }
}

describe('routeSubmission', () => {
  it('停止済みルートをV1送信データへ変換する', () => {
    const payload = createRouteSubmissionPayload(
      createStoppedRoute(),
    )

    expect(payload.schemaVersion).toBe(1)
    expect(payload.clientRouteId).toBe('route-1')
    expect(payload.startedAt).toBe(
      '2026-11-10T01:00:00.000Z',
    )
    expect(payload.endedAt).toBe(
      '2026-11-10T01:10:00.000Z',
    )
    expect(payload.samples).toHaveLength(2)
  })

  it('GPSサンプルの時刻をISO 8601形式へ変換する', () => {
    const payload = createRouteSubmissionPayload(
      createStoppedRoute(),
    )

    expect(payload.samples[0].timestamp).toBe(
      '2026-11-10T01:00:01.000Z',
    )
  })

  it('座標とGPS情報を保持する', () => {
    const payload = createRouteSubmissionPayload(
      createStoppedRoute(),
    )

    expect(payload.samples[0]).toEqual({
      latitude: 34.6901,
      longitude: 135.1955,
      accuracyMeters: 10,
      timestamp: '2026-11-10T01:00:01.000Z',
      altitudeMeters: 18.2,
      altitudeAccuracyMeters: 4,
      headingDegrees: 90,
      speedMetersPerSecond: 2.4,
    })
  })

  it('クライアント概要に経過時間と距離を含める', () => {
    const payload = createRouteSubmissionPayload(
      createStoppedRoute(),
    )

    expect(payload.clientSummary.elapsedMs).toBe(600_000)
    expect(payload.clientSummary.distanceMeters).toBeGreaterThan(
      90,
    )
    expect(payload.clientSummary.distanceMeters).toBeLessThan(
      110,
    )
  })

  it('停止されていないルートは変換しない', () => {
    const recordingRoute: RecordedRoute = {
      ...createStoppedRoute(),
      endedAtMs: null,
    }

    expect(() =>
      createRouteSubmissionPayload(recordingRoute),
    ).toThrow(IncompleteRouteError)
  })

  it('送信データに縄張りやポイントを含めない', () => {
    const payload = createRouteSubmissionPayload(
      createStoppedRoute(),
    )

    expect(payload).not.toHaveProperty('territoryOwner')
    expect(payload).not.toHaveProperty('capturedTerritories')
    expect(payload).not.toHaveProperty('points')
    expect(payload).not.toHaveProperty('isValid')
  })
})