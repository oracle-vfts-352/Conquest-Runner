import type {
  GpsSample,
  RecordedRoute,
} from './gpsTypes'

export const MINIMUM_ROUTE_SAMPLE_COUNT = 4

export type CaptureRouteSample = {
  latitude: number
  longitude: number
  timestamp: string
  accuracyMeters: number
}

export type CaptureRouteRequestBody = {
  route: CaptureRouteSample[]
}

export type PreparedRouteSubmission = {
  body: CaptureRouteRequestBody
  idempotencyKey: string
}

export class IncompleteRouteError extends Error {
  constructor() {
    super('停止されていないルートは送信できません。')
    this.name = 'IncompleteRouteError'
  }
}

export class InsufficientRouteSamplesError extends Error {
  constructor() {
    super(
      `ルート送信には最低${MINIMUM_ROUTE_SAMPLE_COUNT}件のGPSサンプルが必要です。`,
    )
    this.name = 'InsufficientRouteSamplesError'
  }
}

export class InvalidRouteTimestampError extends Error {
  constructor() {
    super(
      'GPSサンプルのタイムスタンプは有効かつ厳密な昇順である必要があります。',
    )
    this.name = 'InvalidRouteTimestampError'
  }
}

function hasStrictlyIncreasingTimestamps(
  samples: GpsSample[],
): boolean {
  for (
    let index = 1;
    index < samples.length;
    index += 1
  ) {
    const previousSample = samples[index - 1]
    const currentSample = samples[index]

    if (
      currentSample.timestampMs <=
      previousSample.timestampMs
    ) {
      return false
    }
  }

  return true
}

function hasValidTimestamps(
  samples: GpsSample[],
): boolean {
  return samples.every((sample) =>
    Number.isFinite(sample.timestampMs),
  )
}

export function prepareRouteSubmission(
  route: RecordedRoute,
): PreparedRouteSubmission {
  if (route.endedAtMs === null) {
    throw new IncompleteRouteError()
  }

  if (
    route.samples.length <
    MINIMUM_ROUTE_SAMPLE_COUNT
  ) {
    throw new InsufficientRouteSamplesError()
  }

  if (
    !hasValidTimestamps(route.samples) ||
    !hasStrictlyIncreasingTimestamps(route.samples)
  ) {
    throw new InvalidRouteTimestampError()
  }

  return {
    idempotencyKey: route.id,
    body: {
      route: route.samples.map((sample) => ({
        latitude: sample.latitude,
        longitude: sample.longitude,
        timestamp: new Date(
          sample.timestampMs,
        ).toISOString(),
        accuracyMeters: sample.accuracyMeters,
      })),
    },
  }
}
