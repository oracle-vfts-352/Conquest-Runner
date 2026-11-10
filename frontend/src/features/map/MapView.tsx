import { useEffect, useRef, useState } from 'react'
import mapboxgl, {
  type GeoJSONSource,
  type Map as MapboxMap,
  type Marker,
} from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'
import './MapView.css'
import type { MapViewProps } from './mapTypes'

const ROUTE_SOURCE_ID = 'conquest-runner-routes'
const ROUTE_LAYER_ID = 'conquest-runner-route-lines'

const TERRITORY_SOURCE_ID = 'conquest-runner-territories'
const TERRITORY_FILL_LAYER_ID = 'conquest-runner-territory-fill'
const TERRITORY_OUTLINE_LAYER_ID = 'conquest-runner-territory-outline'

const DEFAULT_CENTER: readonly [number, number] = [135.1955, 34.6901]

// MapViewProps から型を導出し、prop の型と定数の型を必ず一致させる
const EMPTY_ROUTE_DATA: NonNullable<
  MapViewProps['routeLines']
> = {
  type: 'FeatureCollection',
  features: [],
}

const EMPTY_TERRITORY_DATA: NonNullable<
  MapViewProps['territories']
> = {
  type: 'FeatureCollection',
  features: [],
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message
  }

  return '地図を読み込めませんでした。ネットワーク接続とMapbox設定を確認してください。'
}

export function MapView({
  center = DEFAULT_CENTER,
  zoom = 13,
  routeLines = EMPTY_ROUTE_DATA,
  territories = EMPTY_TERRITORY_DATA,
  activePosition = null,
  className,
  onMapReady,
  onMapError,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<MapboxMap | null>(null)
  const markerRef = useRef<Marker | null>(null)
  const isMapReadyRef = useRef(false)

  const routeLinesRef = useRef(routeLines)
  const territoriesRef = useRef(territories)
  const onMapReadyRef = useRef(onMapReady)
  const onMapErrorRef = useRef(onMapError)

  const initialCenterRef = useRef<[number, number]>([
    center[0],
    center[1],
  ])
  const initialZoomRef = useRef(zoom)

  // トークン有無は render 時に確定するため、初期 state で表現する
  const hasAccessToken = Boolean(
    import.meta.env.VITE_MAPBOX_ACCESS_TOKEN,
  )

  const [isLoading, setIsLoading] = useState(hasAccessToken)
  const [errorMessage, setErrorMessage] = useState<string | null>(
    hasAccessToken
      ? null
      : '地図を表示するにはVITE_MAPBOX_ACCESS_TOKENの設定が必要です。',
  )

  const centerLongitude = center[0]
  const centerLatitude = center[1]

  useEffect(() => {
    routeLinesRef.current = routeLines
  }, [routeLines])

  useEffect(() => {
    territoriesRef.current = territories
  }, [territories])

  useEffect(() => {
    onMapReadyRef.current = onMapReady
  }, [onMapReady])

  useEffect(() => {
    onMapErrorRef.current = onMapError
  }, [onMapError])

  // 地図の生成は初回マウント時のみ行う
  useEffect(() => {
    const accessToken =
      import.meta.env.VITE_MAPBOX_ACCESS_TOKEN

    const styleUrl =
      import.meta.env.VITE_MAPBOX_STYLE_URL ||
      'mapbox://styles/mapbox/streets-v12'

    if (!accessToken) {
      // state は render 時に導出済み。ここでは外部通知のみ行う
      const configurationError = new Error(
        'Mapbox公開トークンが設定されていません。',
      )

      onMapErrorRef.current?.(configurationError)

      return
    }

    if (!containerRef.current || mapRef.current) {
      return
    }

    mapboxgl.accessToken = accessToken

    try {
      const map = new mapboxgl.Map({
        container: containerRef.current,
        style: styleUrl,
        center: initialCenterRef.current,
        zoom: initialZoomRef.current,
      })

      mapRef.current = map
      isMapReadyRef.current = false

      map.addControl(
        new mapboxgl.NavigationControl(),
        'top-right',
      )

      map.on('load', () => {
        isMapReadyRef.current = true

        map.addSource(ROUTE_SOURCE_ID, {
          type: 'geojson',
          data: routeLinesRef.current,
        })

        map.addLayer({
          id: ROUTE_LAYER_ID,
          type: 'line',
          source: ROUTE_SOURCE_ID,
          paint: {
            'line-color': [
              'match',
              ['get', 'status'],
              'recording',
              '#dc2626',
              'submitted',
              '#16a34a',
              '#2563eb',
            ],
            'line-width': 5,
            'line-opacity': 0.9,
          },
        })

        map.addSource(TERRITORY_SOURCE_ID, {
          type: 'geojson',
          data: territoriesRef.current,
        })

        map.addLayer({
          id: TERRITORY_FILL_LAYER_ID,
          type: 'fill',
          source: TERRITORY_SOURCE_ID,
          paint: {
            'fill-color': [
              'coalesce',
              ['get', 'fillColor'],
              '#7c3aed',
            ],
            'fill-opacity': 0.3,
          },
        })

        map.addLayer({
          id: TERRITORY_OUTLINE_LAYER_ID,
          type: 'line',
          source: TERRITORY_SOURCE_ID,
          paint: {
            'line-color': [
              'coalesce',
              ['get', 'outlineColor'],
              '#5b21b6',
            ],
            'line-width': 2,
          },
        })

        setIsLoading(false)
        setErrorMessage(null)
        onMapReadyRef.current?.()
      })

      map.on('error', (event) => {
        const mapError =
          event.error instanceof Error
            ? event.error
            : new Error(
                'Mapbox地図の読み込みに失敗しました。',
              )

        onMapErrorRef.current?.(mapError)

        // 初回 style 読み込み失敗のみ致命扱い
        if (!isMapReadyRef.current) {
          setIsLoading(false)
          setErrorMessage(getErrorMessage(mapError))
        }
      })
    } catch (error) {
      const initializationError =
        error instanceof Error
          ? error
          : new Error(
              'Mapbox地図を初期化できませんでした。',
            )

      // effect 本体での同期的な setState を避ける
      queueMicrotask(() => {
        setIsLoading(false)
        setErrorMessage(
          getErrorMessage(initializationError),
        )
        onMapErrorRef.current?.(initializationError)
      })
    }

    return () => {
      isMapReadyRef.current = false

      markerRef.current?.remove()
      markerRef.current = null

      mapRef.current?.remove()
      mapRef.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current

    if (!map) {
      return
    }

    map.setCenter([centerLongitude, centerLatitude])
    map.setZoom(zoom)
  }, [centerLatitude, centerLongitude, zoom])

  useEffect(() => {
    const map = mapRef.current

    if (!map) {
      return
    }

    const routeSource = map.getSource(
      ROUTE_SOURCE_ID,
    ) as GeoJSONSource | undefined

    if (!routeSource) {
      return
    }

    routeSource.setData(routeLines)
  }, [routeLines])

  useEffect(() => {
    const map = mapRef.current

    if (!map) {
      return
    }

    const territorySource = map.getSource(
      TERRITORY_SOURCE_ID,
    ) as GeoJSONSource | undefined

    if (!territorySource) {
      return
    }

    territorySource.setData(territories)
  }, [territories])

  useEffect(() => {
    const map = mapRef.current

    if (!map) {
      return
    }

    if (!activePosition) {
      markerRef.current?.remove()
      markerRef.current = null

      return
    }

    const coordinates: [number, number] = [
      activePosition.longitude,
      activePosition.latitude,
    ]

    if (markerRef.current) {
      markerRef.current.setLngLat(coordinates)

      return
    }

    const markerElement = document.createElement('div')

    markerElement.className =
      'map-view__position-marker'

    markerElement.setAttribute(
      'aria-label',
      '現在位置',
    )

    markerRef.current = new mapboxgl.Marker({
      element: markerElement,
    })
      .setLngLat(coordinates)
      .addTo(map)
  }, [activePosition])

  const rootClassName = ['map-view', className]
    .filter(Boolean)
    .join(' ')

  return (
    <section
      className={rootClassName}
      aria-label="ConquestRunnerの地図"
    >
      <div
        ref={containerRef}
        className="map-view__canvas"
      />

      {isLoading && !errorMessage ? (
        <div
          className="map-view__status"
          role="status"
          aria-live="polite"
        >
          <div>
            <p className="map-view__status-title">
              地図を読み込んでいます
            </p>

            <p className="map-view__status-message">
              しばらくお待ちください。
            </p>
          </div>
        </div>
      ) : null}

      {errorMessage ? (
        <div
          className="map-view__status map-view__status--error"
          role="alert"
        >
          <div>
            <p className="map-view__status-title">
              地図を表示できません
            </p>

            <p className="map-view__status-message">
              {errorMessage}
            </p>
          </div>
        </div>
      ) : null}
    </section>
  )
}

export default MapView