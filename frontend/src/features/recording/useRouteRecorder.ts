import { useCallback, useEffect, useRef, useState } from 'react'
import type {
  GpsSample,
  RecordedRoute,
  RecorderStatus,
  RecordingStopReason,
  RouteRecorderError,
} from './gpsTypes'

export type UseRouteRecorderOptions = {
  enableHighAccuracy?: boolean
  timeoutMs?: number
  maximumAgeMs?: number
}

export type RouteRecorderApi = {
  status: RecorderStatus
  route: RecordedRoute | null
  latestSample: GpsSample | null
  error: RouteRecorderError | null
  warning: string | null
  start: () => void
  stop: () => void
  discard: () => void
}

const DEFAULT_OPTIONS: Required<UseRouteRecorderOptions> = {
  enableHighAccuracy: true,
  timeoutMs: 10_000,
  maximumAgeMs: 0,
}

const POOR_ACCURACY_THRESHOLD_METERS = 50

function createRouteId(): string {
  if (
    typeof crypto !== 'undefined' &&
    typeof crypto.randomUUID === 'function'
  ) {
    return crypto.randomUUID()
  }

  return `route-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function toGpsSample(position: GeolocationPosition): GpsSample {
  return {
    latitude: position.coords.latitude,
    longitude: position.coords.longitude,
    accuracyMeters: position.coords.accuracy,
    timestampMs: position.timestamp,
    altitudeMeters: position.coords.altitude,
    altitudeAccuracyMeters: position.coords.altitudeAccuracy,
    headingDegrees: position.coords.heading,
    speedMetersPerSecond: position.coords.speed,
  }
}

function mapGeolocationError(
  error: GeolocationPositionError,
): {
  recorderError: RouteRecorderError
  stopReason: RecordingStopReason
} {
  switch (error.code) {
    case error.PERMISSION_DENIED:
      return {
        recorderError: {
          code: 'permission-denied',
          message:
            '位置情報の利用が許可されていません。ブラウザー設定を確認してください。',
        },
        stopReason: 'permission-denied',
      }

    case error.POSITION_UNAVAILABLE:
      return {
        recorderError: {
          code: 'position-unavailable',
          message:
            '現在地を取得できません。端末の位置情報設定を確認してください。',
        },
        stopReason: 'position-unavailable',
      }

    case error.TIMEOUT:
      return {
        recorderError: {
          code: 'timeout',
          message:
            '時間内に現在地を取得できませんでした。もう一度お試しください。',
        },
        stopReason: 'timeout',
      }

    default:
      return {
        recorderError: {
          code: 'tracking-interrupted',
          message:
            '位置情報の追跡が中断されました。記録内容を確認してください。',
        },
        stopReason: 'tracking-interrupted',
      }
  }
}

export function useRouteRecorder(
  options: UseRouteRecorderOptions = {},
): RouteRecorderApi {
  const [status, setStatus] = useState<RecorderStatus>('idle')
  const [route, setRoute] = useState<RecordedRoute | null>(null)
  const [latestSample, setLatestSample] =
    useState<GpsSample | null>(null)
  const [error, setError] =
    useState<RouteRecorderError | null>(null)
  const [warning, setWarning] = useState<string | null>(null)

  const watchIdRef = useRef<number | null>(null)

  const clearActiveWatch = useCallback(() => {
    if (
      watchIdRef.current !== null &&
      typeof navigator !== 'undefined' &&
      navigator.geolocation
    ) {
      navigator.geolocation.clearWatch(watchIdRef.current)
      watchIdRef.current = null
    }
  }, [])

  const finishRecording = useCallback(
    (stopReason: RecordingStopReason) => {
      clearActiveWatch()

      setRoute((currentRoute) => {
        if (!currentRoute) {
          return currentRoute
        }

        return {
          ...currentRoute,
          endedAtMs: Date.now(),
          stopReason,
        }
      })
    },
    [clearActiveWatch],
  )

  const start = useCallback(() => {
    if (
      typeof navigator === 'undefined' ||
      !navigator.geolocation
    ) {
      setStatus('error')
      setError({
        code: 'unsupported',
        message:
          'このブラウザーはGPS記録に対応していません。',
      })
      return
    }

    if (watchIdRef.current !== null) {
      return
    }

    const startedAtMs = Date.now()

    setStatus('requesting-permission')
    setError(null)
    setWarning(null)
    setLatestSample(null)
    setRoute({
      id: createRouteId(),
      startedAtMs,
      endedAtMs: null,
      samples: [],
    })

    const watchId = navigator.geolocation.watchPosition(
      (position) => {
        const sample = toGpsSample(position)

        setRoute((currentRoute) => {
          if (!currentRoute) {
            return currentRoute
          }

          return {
            ...currentRoute,
            samples: [...currentRoute.samples, sample],
          }
        })

        setLatestSample(sample)
        setStatus('recording')
        setError(null)

        if (
          !Number.isFinite(sample.accuracyMeters) ||
          sample.accuracyMeters < 0 ||
          sample.accuracyMeters >
            POOR_ACCURACY_THRESHOLD_METERS
        ) {
          setWarning(
            'GPS精度が低下しています。開けた場所へ移動してください。',
          )
        } else {
          setWarning(null)
        }
      },
      (geolocationError) => {
        const mappedError =
          mapGeolocationError(geolocationError)

        finishRecording(mappedError.stopReason)
        setStatus('error')
        setError(mappedError.recorderError)
      },
      {
        enableHighAccuracy:
          options.enableHighAccuracy ??
          DEFAULT_OPTIONS.enableHighAccuracy,
        timeout:
          options.timeoutMs ?? DEFAULT_OPTIONS.timeoutMs,
        maximumAge:
          options.maximumAgeMs ??
          DEFAULT_OPTIONS.maximumAgeMs,
      },
    )

    watchIdRef.current = watchId
  }, [
    finishRecording,
    options.enableHighAccuracy,
    options.maximumAgeMs,
    options.timeoutMs,
  ])

  const stop = useCallback(() => {
    if (watchIdRef.current === null) {
      return
    }

    finishRecording('user')
    setStatus('stopped')
  }, [finishRecording])

  const discard = useCallback(() => {
    clearActiveWatch()
    setStatus('idle')
    setRoute(null)
    setLatestSample(null)
    setError(null)
    setWarning(null)
  }, [clearActiveWatch])

  useEffect(() => {
    return () => {
      clearActiveWatch()
    }
  }, [clearActiveWatch])

  return {
    status,
    route,
    latestSample,
    error,
    warning,
    start,
    stop,
    discard,
  }
}