import type {
  GpsSample,
  RecordedRoute,
} from './gpsTypes'

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

export class EmptyRouteError extends Error {
  constructor() {
    super('GPSサンプルがないルートは送信できません。')
    this.name = 'EmptyRouteError'
  }
}

export class InvalidRouteTimestampError extends Error {
  constructor() {
    super(
      'GPSサンプルのタイムスタンプは厳密な昇順である必要があります。',
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
    if (
      samples[index].timestampMs <=
      samples[index - 1].timestampMs
    ) {
      return false
    }
  }

  return true
}

export function prepareRouteSubmission(
  route: RecordedRoute,
): PreparedRouteSubmission {
  if (route.endedAtMs === null) {
    throw new IncompleteRouteError()
  }

  if (route.samples.length === 0) {
    throw new EmptyRouteError()
  }

  if (!hasStrictlyIncreasingTimestamps(route.samples)) {
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