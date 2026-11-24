export type GpsSample = {
  latitude: number
  longitude: number
  accuracyMeters: number
  timestampMs: number
  altitudeMeters?: number | null
  altitudeAccuracyMeters?: number | null
  headingDegrees?: number | null
  speedMetersPerSecond?: number | null
}

export type RecorderStatus =
  | 'idle'
  | 'requesting-permission'
  | 'recording'
  | 'stopped'
  | 'error'

export type RecordingStopReason =
  | 'user'
  | 'permission-denied'
  | 'position-unavailable'
  | 'timeout'
  | 'tracking-interrupted'

export type RecordedRoute = {
  id: string
  startedAtMs: number
  endedAtMs: number | null
  samples: GpsSample[]
  stopReason?: RecordingStopReason
}

export type RouteSummary = {
  elapsedMs: number
  distanceMeters: number
  acceptedSampleCount: number
  rejectedSampleCount: number
}

export type RouteRecorderErrorCode =
  | 'permission-denied'
  | 'position-unavailable'
  | 'timeout'
  | 'unsupported'
  | 'tracking-interrupted'

export type RouteRecorderError = {
  code: RouteRecorderErrorCode
  message: string
}