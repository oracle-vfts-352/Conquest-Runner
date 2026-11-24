import { describe, expect, it } from 'vitest'
import type { RecordedRoute } from './gpsTypes'
import {
  EmptyRouteError,
  IncompleteRouteError,
  InvalidRouteTimestampError,
  prepareRouteSubmission,
} from './routeSubmission'

function createStoppedRoute(): RecordedRoute {
  return {
    id: 'route-1',
    startedAtMs: Date.UTC(2026, 10, 24, 0, 0, 0),
    endedAtMs: Date.UTC(2026, 10, 24, 0, 10, 0),
    stopReason: 'user',
    samples: [
      {
        latitude: 34.6901,
        longitude: 135.1955,
        accuracyMeters: 10,
        timestampMs: Date.UTC(
          2026,
          10,
          24,
          0,
          0,
          1,
        ),
        altitudeMeters: 18.2,
        altitudeAccuracyMeters: 4,
        headingDegrees: 90,
        speedMetersPerSecond: 2.4,
      },
      {
        latitude: 34.691,
        longitude: 135.196,
        accuracyMeters: 12,
        timestampMs: Date.UTC(
          2026,
          10,
          24,
          0,
          0,
          2,
        ),
      },
    ],
  }
}

describe('routeSubmission', () => {
  it('バックエンド契約と一致する本文を作成する', () => {
    const submission = prepareRouteSubmission(
      createStoppedRoute(),
    )

    expect(submission.body).toEqual({
      route: [
        {
          latitude: 34.6901,
          longitude: 135.1955,
          timestamp: '2026-11-24T00:00:01.000Z',
          accuracyMeters: 10,
        },
        {
          latitude: 34.691,
          longitude: 135.196,
          timestamp: '2026-11-24T00:00:02.000Z',
          accuracyMeters: 12,
        },
      ],
    })
  })

  it('ルートIDをIdempotency-Key用に返す', () => {
    const submission = prepareRouteSubmission(
      createStoppedRoute(),
    )

    expect(submission.idempotencyKey).toBe('route-1')
  })

  it('タイムスタンプをUTCのISO 8601形式にする', () => {
    const submission = prepareRouteSubmission(
      createStoppedRoute(),
    )

    expect(
      submission.body.route[0].timestamp,
    ).toBe('2026-11-24T00:00:01.000Z')

    expect(
      submission.body.route[0].timestamp.endsWith('Z'),
    ).toBe(true)
  })

  it('本文に不許可の追加フィールドを含めない', () => {
    const submission = prepareRouteSubmission(
      createStoppedRoute(),
    )

    expect(Object.keys(submission.body)).toEqual([
      'route',
    ])

    expect(submission.body).not.toHaveProperty(
      'schemaVersion',
    )
    expect(submission.body).not.toHaveProperty(
      'clientRouteId',
    )
    expect(submission.body).not.toHaveProperty(
      'startedAt',
    )
    expect(submission.body).not.toHaveProperty(
      'endedAt',
    )
    expect(submission.body).not.toHaveProperty(
      'clientSummary',
    )
  })

  it('各サンプルに4項目だけを含める', () => {
    const submission = prepareRouteSubmission(
      createStoppedRoute(),
    )

    expect(
      Object.keys(submission.body.route[0]).sort(),
    ).toEqual(
      [
        'accuracyMeters',
        'latitude',
        'longitude',
        'timestamp',
      ].sort(),
    )

    expect(
      submission.body.route[0],
    ).not.toHaveProperty('altitudeMeters')

    expect(
      submission.body.route[0],
    ).not.toHaveProperty('headingDegrees')

    expect(
      submission.body.route[0],
    ).not.toHaveProperty(
      'speedMetersPerSecond',
    )
  })

  it('停止されていないルートを拒否する', () => {
    const route: RecordedRoute = {
      ...createStoppedRoute(),
      endedAtMs: null,
    }

    expect(() =>
      prepareRouteSubmission(route),
    ).toThrow(IncompleteRouteError)
  })

  it('GPSサンプルが空のルートを拒否する', () => {
    const route: RecordedRoute = {
      ...createStoppedRoute(),
      samples: [],
    }

    expect(() =>
      prepareRouteSubmission(route),
    ).toThrow(EmptyRouteError)
  })

  it('同じタイムスタンプがあるルートを拒否する', () => {
    const route = createStoppedRoute()

    route.samples[1].timestampMs =
      route.samples[0].timestampMs

    expect(() =>
      prepareRouteSubmission(route),
    ).toThrow(InvalidRouteTimestampError)
  })

  it('タイムスタンプが逆転したルートを拒否する', () => {
    const route = createStoppedRoute()

    route.samples[1].timestampMs =
      route.samples[0].timestampMs - 1

    expect(() =>
      prepareRouteSubmission(route),
    ).toThrow(InvalidRouteTimestampError)
  })
})