import { act, renderHook } from '@testing-library/react'
import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest'
import { useRouteRecorder } from './useRouteRecorder'

type SuccessCallback = PositionCallback
type ErrorCallback = PositionErrorCallback

let successCallback: SuccessCallback
let errorCallback: ErrorCallback

const watchPositionMock = vi.fn(
  (
    success: SuccessCallback,
    error: ErrorCallback,
  ): number => {
    successCallback = success
    errorCallback = error
    return 42
  },
)

const clearWatchMock = vi.fn()

function createPosition(
  overrides: Partial<GeolocationCoordinates> = {},
): GeolocationPosition {
  const coords: GeolocationCoordinates = {
    latitude: 34.6901,
    longitude: 135.1955,
    accuracy: 10,
    altitude: null,
    altitudeAccuracy: null,
    heading: null,
    speed: null,
    toJSON: () => ({}),
    ...overrides,
  }

  return {
    coords,
    timestamp: 1_700_000_000_000,
    toJSON: () => ({}),
  }
}

function createGeolocationError(
  code: number,
): GeolocationPositionError {
  return {
    code,
    message: 'test geolocation error',
    PERMISSION_DENIED: 1,
    POSITION_UNAVAILABLE: 2,
    TIMEOUT: 3,
  }
}

describe('useRouteRecorder', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    Object.defineProperty(
      navigator,
      'geolocation',
      {
        configurable: true,
        value: {
          watchPosition: watchPositionMock,
          clearWatch: clearWatchMock,
          getCurrentPosition: vi.fn(),
        },
      },
    )
  })

  it('startを呼ぶまで位置情報を要求しない', () => {
    renderHook(() => useRouteRecorder())

    expect(watchPositionMock).not.toHaveBeenCalled()
  })

  it('記録を開始してGPSサンプルを保存する', () => {
    const { result } = renderHook(() =>
      useRouteRecorder(),
    )

    act(() => {
      result.current.start()
    })

    expect(result.current.status).toBe(
      'requesting-permission',
    )
    expect(watchPositionMock).toHaveBeenCalledTimes(1)

    act(() => {
      successCallback(createPosition())
    })

    expect(result.current.status).toBe('recording')
    expect(result.current.route?.samples).toHaveLength(1)
    expect(result.current.route?.samples[0]).toEqual({
      latitude: 34.6901,
      longitude: 135.1955,
      accuracyMeters: 10,
      timestampMs: 1_700_000_000_000,
      altitudeMeters: null,
      altitudeAccuracyMeters: null,
      headingDegrees: null,
      speedMetersPerSecond: null,
    })
  })

  it('記録を停止するとclearWatchを呼ぶ', () => {
    const { result } = renderHook(() =>
      useRouteRecorder(),
    )

    act(() => {
      result.current.start()
    })

    act(() => {
      successCallback(createPosition())
    })

    act(() => {
      result.current.stop()
    })

    expect(clearWatchMock).toHaveBeenCalledWith(42)
    expect(result.current.status).toBe('stopped')
    expect(result.current.route?.stopReason).toBe('user')
    expect(result.current.route?.endedAtMs).not.toBeNull()
  })

  it('記録を破棄して初期状態へ戻す', () => {
    const { result } = renderHook(() =>
      useRouteRecorder(),
    )

    act(() => {
      result.current.start()
    })

    act(() => {
      successCallback(createPosition())
    })

    act(() => {
      result.current.discard()
    })

    expect(clearWatchMock).toHaveBeenCalledWith(42)
    expect(result.current.status).toBe('idle')
    expect(result.current.route).toBeNull()
    expect(result.current.latestSample).toBeNull()
    expect(result.current.error).toBeNull()
    expect(result.current.warning).toBeNull()
  })

  it('位置情報が拒否された場合にエラーを表示する', () => {
    const { result } = renderHook(() =>
      useRouteRecorder(),
    )

    act(() => {
      result.current.start()
    })

    act(() => {
      errorCallback(createGeolocationError(1))
    })

    expect(result.current.status).toBe('error')
    expect(result.current.error?.code).toBe(
      'permission-denied',
    )
    expect(result.current.route?.stopReason).toBe(
      'permission-denied',
    )
  })

  it('位置情報が利用できない場合にエラーを表示する', () => {
    const { result } = renderHook(() =>
      useRouteRecorder(),
    )

    act(() => {
      result.current.start()
    })

    act(() => {
      errorCallback(createGeolocationError(2))
    })

    expect(result.current.status).toBe('error')
    expect(result.current.error?.code).toBe(
      'position-unavailable',
    )
  })

  it('位置情報取得がタイムアウトした場合にエラーを表示する', () => {
    const { result } = renderHook(() =>
      useRouteRecorder(),
    )

    act(() => {
      result.current.start()
    })

    act(() => {
      errorCallback(createGeolocationError(3))
    })

    expect(result.current.status).toBe('error')
    expect(result.current.error?.code).toBe('timeout')
  })

  it('GPS精度が50メートルを超える場合に警告する', () => {
    const { result } = renderHook(() =>
      useRouteRecorder(),
    )

    act(() => {
      result.current.start()
    })

    act(() => {
      successCallback(
        createPosition({
          accuracy: 80,
        }),
      )
    })

    expect(result.current.warning).toContain(
      'GPS精度が低下',
    )
  })

  it('アンマウント時にGPS監視を解除する', () => {
    const { result, unmount } = renderHook(() =>
      useRouteRecorder(),
    )

    act(() => {
      result.current.start()
    })

    unmount()

    expect(clearWatchMock).toHaveBeenCalledWith(42)
  })
})