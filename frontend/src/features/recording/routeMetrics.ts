import type {
  GpsSample,
  RecordedRoute,
  RouteSummary,
} from './gpsTypes'

const EARTH_RADIUS_METERS = 6_371_000

export const DEFAULT_MAX_ACCURACY_METERS = 50

function degreesToRadians(degrees: number): number {
  return (degrees * Math.PI) / 180
}

export function calculateDistanceMeters(
  start: GpsSample,
  end: GpsSample,
): number {
  const startLatitude = degreesToRadians(start.latitude)
  const endLatitude = degreesToRadians(end.latitude)
  const latitudeDifference = degreesToRadians(
    end.latitude - start.latitude,
  )
  const longitudeDifference = degreesToRadians(
    end.longitude - start.longitude,
  )

  const haversine =
    Math.sin(latitudeDifference / 2) ** 2 +
    Math.cos(startLatitude) *
      Math.cos(endLatitude) *
      Math.sin(longitudeDifference / 2) ** 2

  const angularDistance =
    2 *
    Math.atan2(
      Math.sqrt(haversine),
      Math.sqrt(1 - haversine),
    )

  return EARTH_RADIUS_METERS * angularDistance
}

export function isSampleAccurate(
  sample: GpsSample,
  maximumAccuracyMeters = DEFAULT_MAX_ACCURACY_METERS,
): boolean {
  return (
    Number.isFinite(sample.accuracyMeters) &&
    sample.accuracyMeters >= 0 &&
    sample.accuracyMeters <= maximumAccuracyMeters
  )
}

export function calculateRouteDistanceMeters(
  samples: GpsSample[],
  maximumAccuracyMeters = DEFAULT_MAX_ACCURACY_METERS,
): number {
  const acceptedSamples = samples.filter((sample) =>
    isSampleAccurate(sample, maximumAccuracyMeters),
  )

  if (acceptedSamples.length < 2) {
    return 0
  }

  let totalDistanceMeters = 0

  for (
    let index = 1;
    index < acceptedSamples.length;
    index += 1
  ) {
    totalDistanceMeters += calculateDistanceMeters(
      acceptedSamples[index - 1],
      acceptedSamples[index],
    )
  }

  return totalDistanceMeters
}

export function createRouteSummary(
  route: RecordedRoute,
  maximumAccuracyMeters = DEFAULT_MAX_ACCURACY_METERS,
): RouteSummary {
  const acceptedSampleCount = route.samples.filter((sample) =>
    isSampleAccurate(sample, maximumAccuracyMeters),
  ).length

  const endTimeMs = route.endedAtMs ?? Date.now()

  return {
    elapsedMs: Math.max(
      0,
      endTimeMs - route.startedAtMs,
    ),
    distanceMeters: calculateRouteDistanceMeters(
      route.samples,
      maximumAccuracyMeters,
    ),
    acceptedSampleCount,
    rejectedSampleCount:
      route.samples.length - acceptedSampleCount,
  }
}