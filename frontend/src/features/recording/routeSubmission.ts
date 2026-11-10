import type { RecordedRoute } from './gpsTypes'
import { createRouteSummary } from './routeMetrics'

export type RouteSubmissionSampleV1 = {
  latitude: number
  longitude: number
  accuracyMeters: number
  timestamp: string
  altitudeMeters?: number | null
  altitudeAccuracyMeters?: number | null
  headingDegrees?: number | null
  speedMetersPerSecond?: number | null
}

export type RouteSubmissionPayloadV1 = {
  schemaVersion: 1
  clientRouteId: string
  startedAt: string
  endedAt: string
  samples: RouteSubmissionSampleV1[]
  clientSummary: {
    elapsedMs: number
    distanceMeters: number
  }
}

export class IncompleteRouteError extends Error {
  constructor() {
    super('停止されていないルートは送信用データに変換できません。')
    this.name = 'IncompleteRouteError'
  }
}

export function createRouteSubmissionPayload(
  route: RecordedRoute,
): RouteSubmissionPayloadV1 {
  if (route.endedAtMs === null) {
    throw new IncompleteRouteError()
  }

  const summary = createRouteSummary(route)

  return {
    schemaVersion: 1,
    clientRouteId: route.id,
    startedAt: new Date(route.startedAtMs).toISOString(),
    endedAt: new Date(route.endedAtMs).toISOString(),
    samples: route.samples.map((sample) => ({
      latitude: sample.latitude,
      longitude: sample.longitude,
      accuracyMeters: sample.accuracyMeters,
      timestamp: new Date(sample.timestampMs).toISOString(),
      altitudeMeters: sample.altitudeMeters,
      altitudeAccuracyMeters: sample.altitudeAccuracyMeters,
      headingDegrees: sample.headingDegrees,
      speedMetersPerSecond: sample.speedMetersPerSecond,
    })),
    clientSummary: {
      elapsedMs: summary.elapsedMs,
      distanceMeters: summary.distanceMeters,
    },
  }
}