import { useMemo, useState } from 'react'
import {
  ArrowLeft,
  Search,
  Snowflake,
  MapPin,
  Satellite,
  X,
} from 'lucide-react'
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Popup,
  useMap,
} from 'react-leaflet'
import type { LatLngExpression } from 'leaflet'
import 'leaflet/dist/leaflet.css'

type Glacier = {
  name: string
  region: string
  country: string
  lat: number
  lng: number
  id: string
}

const glaciers: Glacier[] = [
  {
    name: 'Gangotri Glacier',
    region: 'Himalayas',
    country: 'India',
    lat: 30.87,
    lng: 79.08,
    id: 'RGI60-14.06794',
  },
  {
    name: 'Khumbu Glacier',
    region: 'Himalayas',
    country: 'Nepal',
    lat: 27.98,
    lng: 86.92,
    id: 'RGI60-15.03733',
  },
  {
    name: 'Aletsch Glacier',
    region: 'Swiss Alps',
    country: 'Switzerland',
    lat: 46.48,
    lng: 8.03,
    id: 'RGI60-11.01238',
  },
  {
    name: 'Perito Moreno Glacier',
    region: 'Patagonia',
    country: 'Argentina',
    lat: -50.49,
    lng: -73.05,
    id: 'RGI60-17.03596',
  },
  {
    name: 'Columbia Glacier',
    region: 'Alaska',
    country: 'United States',
    lat: 61.08,
    lng: -146.75,
    id: 'RGI60-01.00570',
  },
  {
    name: 'Vatnajökull',
    region: 'Iceland',
    country: 'Iceland',
    lat: 64.42,
    lng: -16.85,
    id: 'RGI60-06.00001',
  },
]

function FlyToSelected({
  glacier,
}: {
  glacier: Glacier | null
}) {
  const map = useMap()

  if (glacier) {
    map.flyTo(
      [glacier.lat, glacier.lng] as LatLngExpression,
      8,
      {
        duration: 1,
      },
    )
  }

  return null
}

function Explore({
  onBack,
}: {
  onBack: () => void
}) {
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Glacier | null>(null)

  const results = useMemo(() => {
    const query = search.trim().toLowerCase()

    if (!query) {
      return glaciers
    }

    return glaciers.filter(
      (glacier) =>
        glacier.name.toLowerCase().includes(query) ||
        glacier.region.toLowerCase().includes(query) ||
        glacier.country.toLowerCase().includes(query) ||
        glacier.id.toLowerCase().includes(query),
    )
  }, [search])

  const selectGlacier = (glacier: Glacier) => {
    setSelected(glacier)
    setSearch(glacier.name)
  }

  return (
    <div className="explore-page">
      {/* TOP BAR */}

      <header className="explore-header">
        <button className="back-button" onClick={onBack}>
          <ArrowLeft size={18} />
          Back to GlacierAI
        </button>

        <div className="explore-title">
          <div className="explore-logo">
            <Snowflake size={20} />
          </div>

          <div>
            <strong>Explore Glaciers</strong>
            <span>Global Glacier Inventory</span>
          </div>
        </div>
      </header>

      {/* CONTENT */}

      <main className="explore-content">
        <section className="explore-intro">
          <div>
            <div className="eyebrow">GLOBAL EXPLORER</div>

            <h1>
              Explore glaciers
              <span> worldwide.</span>
            </h1>

            <p>
              Search for a glacier, region, country or RGI identifier
              and select a study area for satellite-based analysis.
            </p>
          </div>
        </section>

        {/* SEARCH */}

        <section className="explorer-search-section">
          <div className="explorer-search">
            <Search size={20} />

            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search any glacier, region, country or RGI ID..."
            />

            {search && (
              <button
                className="clear-search"
                onClick={() => setSearch('')}
              >
                <X size={17} />
              </button>
            )}
          </div>

          <div className="search-count">
            {search
              ? `${results.length} matching glacier${
                  results.length === 1 ? '' : 's'
                }`
              : `${glaciers.length} example glaciers displayed`}
          </div>
        </section>

        {/* MAP + RESULTS */}

        <section className="explorer-layout">

          {/* RESULTS */}

          <aside className="glacier-results">

            <div className="results-heading">
              <div>
                <strong>Glacier Inventory</strong>
                <span>Select a glacier to view its location.</span>
              </div>
            </div>

            <div className="results-list">
              {results.length === 0 ? (
                <div className="empty-results">
                  <Snowflake size={28} />

                  <strong>No glacier found</strong>

                  <p>
                    Try another glacier name, region,
                    country or RGI ID.
                  </p>
                </div>
              ) : (
                results.map((glacier) => (
                  <button
                    key={glacier.id}
                    className={`glacier-result ${
                      selected?.id === glacier.id
                        ? 'selected-result'
                        : ''
                    }`}
                    onClick={() => selectGlacier(glacier)}
                  >
                    <div className="result-symbol">
                      <Snowflake size={17} />
                    </div>

                    <div className="result-info">
                      <strong>{glacier.name}</strong>

                      <span>
                        {glacier.region} · {glacier.country}
                      </span>

                      <small>{glacier.id}</small>
                    </div>
                  </button>
                ))
              )}
            </div>
          </aside>

          {/* MAP */}

          <div className="explorer-map-container">
            <MapContainer
              center={[25, 20]}
              zoom={2}
              minZoom={2}
              maxZoom={12}
              scrollWheelZoom
              className="explorer-map"
            >
              <TileLayer
                attribution='&copy; OpenStreetMap contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />

              <FlyToSelected glacier={selected} />

              {glaciers.map((glacier) => (
                <CircleMarker
                  key={glacier.id}
                  center={[glacier.lat, glacier.lng]}
                  radius={selected?.id === glacier.id ? 10 : 7}
                  pathOptions={{
                    color:
                      selected?.id === glacier.id
                        ? '#0e5f9f'
                        : '#1677c8',
                    fillColor: '#1677c8',
                    fillOpacity: 0.8,
                  }}
                  eventHandlers={{
                    click: () => selectGlacier(glacier),
                  }}
                >
                  <Popup>
                    <strong>{glacier.name}</strong>

                    <br />

                    {glacier.region}, {glacier.country}

                    <br />

                    <br />

                    <button
                      className="popup-button"
                      onClick={() => selectGlacier(glacier)}
                    >
                      Select glacier
                    </button>
                  </Popup>
                </CircleMarker>
              ))}
            </MapContainer>

            <div className="map-info">
              <span>
                <span className="map-dot" />
                Glacier inventory
              </span>

              <span>
                <MapPin size={13} />
                Click a marker
              </span>
            </div>
          </div>
        </section>

        {/* SELECTED GLACIER */}

        {selected && (
          <section className="selected-glacier-panel">
            <div className="selected-glacier-icon">
              <Snowflake size={25} />
            </div>

            <div className="selected-glacier-info">
              <div className="eyebrow">SELECTED STUDY AREA</div>

              <h2>{selected.name}</h2>

              <p>
                {selected.region} · {selected.country}
              </p>

              <div className="selected-meta">
                <span>
                  <MapPin size={14} />
                  {selected.lat.toFixed(4)},{' '}
                  {selected.lng.toFixed(4)}
                </span>

                <span>RGI ID: {selected.id}</span>
              </div>
            </div>

            <button className="primary-button">
              <Satellite size={17} />
              View Satellite Data
            </button>
          </section>
        )}

        {/* INFORMATION */}

        <section className="explorer-note">
          <div className="note-icon">
            <Satellite size={21} />
          </div>

          <div>
            <strong>Next step: satellite observations</strong>

            <p>
              After selecting a glacier, GlacierAI will retrieve
              available satellite observations for the selected
              study area and time period.
            </p>
          </div>
        </section>
      </main>
    </div>
  )
}

export default Explore