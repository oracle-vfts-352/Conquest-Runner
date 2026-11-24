import { describe, expect, it } from 'vitest'
import type { RecordedRoute } from './gpsTypes'
import {
  IncompleteRouteError,
  InsufficientRouteSamplesError,
  InvalidRouteTimestampError,
  MINIMUM_ROUTE_SAMPLE_COUNT,
  prepareRouteSubmission,
} from './routeSubmission'

function createStoppedRoute(): RecordedRoute {
  return {
    id: 'route-1',
    startedAtMs: Date.UTC(
      2026,
      10,
      24,
      0,
      0,
      0,
    ),
    endedAtMs: Date.UTC(
      2026,
      10,
      24,
      0,
      10,
      0,
    ),
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
      {
        latitude: 34.6915,
        longitude: 135.1965,
        accuracyMeters: 11,
        timestampMs: Date.UTC(
          2026,
          10,
          24,
          0,
          0,
          3,
        ),
      },
      {
        latitude: 34.692,
        longitude: 135.197,
        accuracyMeters: 9,
        timestampMs: Date.UTC(
          2026,
          10,
          24,
          0,
          0,
          4,
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
        {
          latitude: 34.6915,
          longitude: 135.1965,
          timestamp: '2026-11-24T00:00:03.000Z',
          accuracyMeters: 11,
        },
        {
          latitude: 34.692,
          longitude: 135.197,
          timestamp: '2026-11-24T00:00:04.000Z',
          accuracyMeters: 9,
        },
      ],
    })
  })

  it('ルートIDをIdempotency-Key用に返す', () => {
    const submission = prepareRouteSubmission(
      createStoppedRoute(),
    )

    expect(submission.idempotencyKey).toBe(
      'route-1',
    )
  })

  it('タイムスタンプをUTC ISO 8601形式にする', () => {
    const submission = prepareRouteSubmission(
      createStoppedRoute(),
    )

    for (const sample of submission.body.route) {
      expect(sample.timestamp).toMatch(
        /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/,
      )
    }
  })

  it('本文のトップレベルにはrouteだけを含める', () => {
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

  it('各サンプルには許可された項目だけを含める', () => {
    const submission = prepareRouteSubmission(
      createStoppedRoute(),
    )

    const expectedKeys = [
      'accuracyMeters',
      'latitude',
      'longitude',
      'timestamp',
    ].sort()

    for (const sample of submission.body.route) {
      expect(Object.keys(sample).sort()).toEqual(
        expectedKeys,
      )
    }

    expect(
      submission.body.route[0],
    ).not.toHaveProperty('altitudeMeters')

    expect(
      submission.body.route[0],
    ).not.toHaveProperty(
      'altitudeAccuracyMeters',
    )

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

  it('4件未満のGPSサンプルを拒否する', () => {
    const route = createStoppedRoute()

    route.samples = route.samples.slice(
      0,
      MINIMUM_ROUTE_SAMPLE_COUNT - 1,
    )

    expect(() =>
      prepareRouteSubmission(route),
    ).toThrow(InsufficientRouteSamplesError)
  })

  it('4件のGPSサンプルを送信できる', () => {
    const route = createStoppedRoute()
    const submission =
      prepareRouteSubmission(route)

    expect(route.samples).toHaveLength(
      MINIMUM_ROUTE_SAMPLE_COUNT,
    )

    expect(submission.body.route).toHaveLength(
      MINIMUM_ROUTE_SAMPLE_COUNT,
    )
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

  it('無効なタイムスタンプを拒否する', () => {
    const route = createStoppedRoute()

    route.samples[0].timestampMs = Number.NaN

    expect(() =>
      prepareRouteSubmission(route),
    ).toThrow(InvalidRouteTimestampError)
  })
})
