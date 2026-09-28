import { useEffect, useRef, useState } from "react";

import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Polygon,
  Popup,
  useMap,
} from "react-leaflet";

import "leaflet/dist/leaflet.css";

import {
  ArrowRight,
  BarChart3,
  CheckCircle2,
  ChevronRight,
  Database,
  Download,
  FileText,
  Globe2,
  Layers3,
  Menu,
  Moon,
  Mountain,
  Search,
  Satellite,
  Settings,
  Snowflake,
  Sun,
  X,
} from "lucide-react";

import "./App.css";


/* =========================================================
   TYPES
========================================================= */

type Theme = "light" | "dark" | "system";


type Glacier = {
  id: string;
  name: string;
  region: string;
  country: string;

  latitude: number;
  longitude: number;

  area: number | null;

  retreatRate?: number;
  elevation?: number;
  status?: "Stable" | "Retreating" | "Rapid Retreat";

  matched_by?: string;
};


/* =========================================================
   SEARCH RESPONSE
========================================================= */

type GlacierSearchResponse = {
  results: Array<{
    id: string;
    name: string;
    latitude: number;
    longitude: number;
    area_km2: number | null;
    region: string;
    country: string;
    matched_by?: string;
  }>;

  count: number;
  query: string;
};


/* =========================================================
   GLACIER GEOMETRY RESPONSE
========================================================= */

type GlacierGeometry =
  | {
      type: "Polygon";
      coordinates: number[][][];
    }
  | {
      type: "MultiPolygon";
      coordinates: number[][][][];
    };


type GlacierGeometryResponse = {
  status: string;

  glacier: {
    id: string;
    name: string;

    latitude: number | null;
    longitude: number | null;

    area_km2: number | null;

    region: string;
    country: string;

    geometry: GlacierGeometry | null;
  };
};


/* =========================================================
   LIVE ANALYSIS RESPONSE
========================================================= */

type LiveAnalysis = {
  status: string;

  glacier: {
    requested_name?: string;
    rgi_id?: string;
    rgi_name?: string;
    name?: string;

    latitude: number;
    longitude: number;

    rgi_area_km2?: number;
    distance_from_input_km?: number;
    matched_by?: string;
  };

  satellite: {
    source: string;
    processing: string;
    aoi_source?: string;

    resolution_m: number;
    crs: string;

    cloud_limit_percent: number;
    observation_window_days: number;

    scene_id?: string | null;
    observation_date?: string | null;
  };

  model: {
    name: string;
    type: string;
    checkpoint: string;
  };

  analysis: {
    glacier_pixels: number;
    total_pixels: number;

    coverage_percent: number;

    area_m2: number;
    area_km2: number;

    rgi_polygon_applied?: boolean;

    xai?: {
      mean_probability: number;
      minimum_probability: number;
      maximum_probability: number;
      threshold: number;

      confidence_distribution_percent: {
        low: number;
        uncertain: number;
        moderate: number;
        high: number;
      };

      pixel_counts: {
        low: number;
        uncertain: number;
        moderate: number;
        high: number;
        total: number;
      };

      explanation: string;
    };
  };

  outputs: {
    mask: string;
    mask_png: string;
    overlay: string;

    probability_heatmap?: string;
    probability_overlay?: string;
    rgi_mask?: string;
  };

  classification?: {
    class?: string;
    display_name?: string;
    confidence?: number;
    confidence_percent?: number;
    probabilities?: Record<string, number>;
    source?: string;
    verification_status?: string;
    verification?: {
      rgi_available?: boolean;
      rgi_glacier_id?: string;
      rgi_glacier_name?: string;
      metadata_source?: string;
      status?: string;
      note?: string;
    };
  };
};


/* =========================================================
   HISTORICAL
========================================================= */

type HistoricalPoint = {
  year: number;
  date: string;
  area_km2: number;

  dice?: number;
  iou?: number;
  coverage_percent?: number;

  rgi_overlap_dice?: number;
  rgi_overlap_iou?: number;
  rgi_coverage_percent?: number;

  area_difference_km2?: number;
  area_difference_percent?: number;

  reliability?: "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN";
};


type GlimsHistoricalRecord = {
  id?: string | number;
  glims_id?: string | null;
  year?: number | null;
  date?: string | null;
  area_km2?: number | null;
  analysis_id?: string | number | null;
  submission_id?: string | number | null;
  status?: string | null;
  source?: string | null;
  glacier_name?: string | null;
  geometry?: unknown;
};

type GlimsReference = {
 
  success?: boolean;
  rgi_id?: string;
  glims_id?: string;
  glims_layer?: string;
  count?: number;
  historical_records?: GlimsHistoricalRecord[];
  message?: string;
};

type HistoricalChange = {
  from_year: number;
  to_year: number;

  from_area_km2: number;
  to_area_km2: number;

  area_change_km2: number;

  percentage_change: number | null;

  annualized_area_change_km2_per_year?: number | null;

  from_reliability: string;
  to_reliability: string;

  suitable_for_retreat?: boolean;

  change_interpretation: string;
};


type ChangeAnalysisData = {
  status?: string;
  glacier?: string;
  analysis_type?: string;
  method?: string;

  quality_summary?: {
    high: number;
    medium: number;
    low: number;
    unknown: number;
    total: number;
  };

  observation_quality?: Array<{
    year: number;
    quality: "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN";
    dice?: number;
    iou?: number;
    rgi_coverage_percent?: number;
    area_difference_percent?: number;
  }>;

  year_to_year_area_change?: HistoricalChange[];

  spatial_boundary_change?: Array<{
    from_year: number;
    to_year: number;
    available: boolean;
    gained_area_km2?: number;
    lost_area_km2?: number;
    changed_area_km2?: number;
    spatial_iou?: number | null;
    note?: string;
    reason?: string;
  }>;

  overall_trend?: {
    status?: string;
    usable_observations?: number;
    total_observations?: number;
    start_year?: number | null;
    end_year?: number | null;
    start_area_km2?: number | null;
    end_area_km2?: number | null;
    area_change_km2?: number | null;
    percentage_change?: number | null;
    annualized_area_change_km2_per_year?: number | null;
    retreat_rate_m_per_year?: number | null;
    trend?: string;
    note?: string;
  };

  scientific_note?: string;
};


type HistoricalAnalysisData = {
  records?: HistoricalPoint[];

  year_to_year_changes?: HistoricalChange[];

  overall_observed_change?: {
    start_year: number;
    end_year: number;

    start_area_km2: number;
    end_area_km2: number;

    total_change_km2: number;

    percentage_change: number | null;

    annualized_change_km2_per_year: number | null;
  };

  reliability_summary?: {
    total_observations: number;

    high_confidence: number;
    medium_confidence: number;
    low_confidence: number;

    reliable_observations: number;

    high_confidence_years: number[];
    medium_confidence_years: number[];
    low_confidence_years: number[];
  };

  trend_assessment?: {
    status: string;
    high_confidence_observations: number;
    note: string;
  };
};


/* =========================================================
   PREDICTION
========================================================= */

type PredictionPoint = {
  year: number;

  predicted_area_km2?: number;
  area_km2?: number;
  predicted?: number;
};


type PredictionResponse = {
  predictions?: PredictionPoint[];
  data?: PredictionPoint[];
  results?: PredictionPoint[];
};


/* =========================================================
   API
========================================================= */

const API = "http://127.0.0.1:8000";


/* =========================================================
   MAP HELPERS
========================================================= */

function polygonToLeafletPositions(
  coordinates: number[][][],
): [number, number][][] {
  return coordinates.map(
    (ring) =>
      ring.map(
        ([lng, lat]) =>
          [lat, lng] as [number, number],
      ),
  );
}


function multiPolygonToLeafletPositions(
  coordinates: number[][][][],
): [number, number][][][] {
  return coordinates.map(
    (polygon) =>
      polygon.map(
        (ring) =>
          ring.map(
            ([lng, lat]) =>
              [lat, lng] as [
                number,
                number,
              ],
          ),
      ),
  );
}


/* =========================================================
   MAP RECENTER
========================================================= */

function RecenterMap({
  latitude,
  longitude,
  geometry,
}: {
  latitude: number;
  longitude: number;

  geometry: GlacierGeometry | null;
}) {
  const map = useMap();


  useEffect(() => {

    if (!geometry) {

      map.flyTo(
        [latitude, longitude],
        7,
        {
          duration: 1.2,
        },
      );

      return;
    }


    try {

      const allPoints: [
        number,
        number,
      ][] = [];


      if (
        geometry.type ===
        "Polygon"
      ) {

        geometry.coordinates.forEach(
          (ring) => {

            ring.forEach(
              ([lng, lat]) => {

                allPoints.push([
                  lat,
                  lng,
                ]);

              },
            );

          },
        );

      } else {

        geometry.coordinates.forEach(
          (polygon) => {

            polygon.forEach(
              (ring) => {

                ring.forEach(
                  ([lng, lat]) => {

                    allPoints.push([
                      lat,
                      lng,
                    ]);

                  },
                );

              },
            );

          },
        );

      }


      if (
        allPoints.length === 0
      ) {

        map.flyTo(
          [latitude, longitude],
          7,
          {
            duration: 1.2,
          },
        );

        return;
      }


      map.fitBounds(
        allPoints,
        {
          padding: [
            50,
            50,
          ],

          maxZoom: 13,

          animate: true,

          duration: 1.2,
        },
      );

    } catch {

      map.flyTo(
        [latitude, longitude],
        7,
        {
          duration: 1.2,
        },
      );

    }

  }, [
    latitude,
    longitude,
    geometry,
    map,
  ]);


  return null;
}


/* =========================================================
   NORMALIZE PREDICTION
========================================================= */

function normalizePrediction(
  payload: unknown,
): PredictionPoint[] {

  /*
   * The prediction API can return either:
   *   [...]
   *   { predictions: [...] }
   *   { data: [...] }
   *   { data: { predictions: [...] } }
   *   { data: { results: [...] } }
   *
   * Always unwrap the response until we reach the
   * actual prediction array. This prevents errors such
   * as "raw.filter is not a function".
   */
  const unwrapPredictionArray = (
    value: unknown,
  ): unknown[] => {

    if (Array.isArray(value)) {
      return value;
    }

    if (!value || typeof value !== "object") {
      return [];
    }

    const object = value as Record<string, unknown>;

    if (Array.isArray(object.predictions)) {
      return object.predictions;
    }

    if (Array.isArray(object.results)) {
      return object.results;
    }

    if (Array.isArray(object.data)) {
      return object.data;
    }

    if (
      object.data &&
      typeof object.data === "object"
    ) {
      return unwrapPredictionArray(object.data);
    }

    return [];
  };

  const raw = unwrapPredictionArray(payload);

  return raw
    .filter(
      (item: unknown) =>
        item !== null &&
        typeof item === "object" &&
        Number.isFinite(
          Number(
            (item as Record<string, unknown>).year,
          ),
        ),
    )
    .map(
      (item: unknown): PredictionPoint => {
        const value =
          item as Record<string, unknown>;

        return {
          year: Number(value.year),
          predicted_area_km2: Number(
            value.predicted_area_km2 ??
              value.area_km2 ??
              value.predicted,
          ),
        };
      },
    )
    .filter(
      (item: PredictionPoint) =>
        Number.isFinite(
          Number(item.predicted_area_km2),
        ),
    )
    .sort(
      (
        a: PredictionPoint,
        b: PredictionPoint,
      ) => a.year - b.year,
    );
}


/* =========================================================
   NORMALIZE HISTORICAL RECORDS
========================================================= */

function normalizeHistoricalRecords(
  rawRecords: unknown,
): HistoricalPoint[] {
  if (!Array.isArray(rawRecords)) return [];

  return rawRecords
    .filter(
      (item: any) =>
        Number.isFinite(Number(item?.year)) &&
        Number.isFinite(Number(item?.area_km2)),
    )
    .map(
      (item: any): HistoricalPoint => ({
        year: Number(item.year),
        date: String(item.date ?? ""),
        area_km2: Number(item.area_km2),

        dice:
          item.dice != null
            ? Number(item.dice)
            : item.validation?.rgi_overlap_dice != null
              ? Number(item.validation.rgi_overlap_dice)
              : undefined,

        iou:
          item.iou != null
            ? Number(item.iou)
            : item.validation?.rgi_overlap_iou != null
              ? Number(item.validation.rgi_overlap_iou)
              : undefined,

        coverage_percent:
          item.coverage_percent != null
            ? Number(item.coverage_percent)
            : item.validation?.rgi_coverage_percent != null
              ? Number(item.validation.rgi_coverage_percent)
              : undefined,

        rgi_overlap_dice:
          item.validation?.rgi_overlap_dice != null
            ? Number(item.validation.rgi_overlap_dice)
            : item.rgi_overlap_dice != null
              ? Number(item.rgi_overlap_dice)
              : undefined,

        rgi_overlap_iou:
          item.validation?.rgi_overlap_iou != null
            ? Number(item.validation.rgi_overlap_iou)
            : item.rgi_overlap_iou != null
              ? Number(item.rgi_overlap_iou)
              : undefined,

        rgi_coverage_percent:
          item.validation?.rgi_coverage_percent != null
            ? Number(item.validation.rgi_coverage_percent)
            : item.rgi_coverage_percent != null
              ? Number(item.rgi_coverage_percent)
              : undefined,

        area_difference_km2:
          item.validation?.area_difference_km2 != null
            ? Number(item.validation.area_difference_km2)
            : item.area_difference_km2 != null
              ? Number(item.area_difference_km2)
              : undefined,

        area_difference_percent:
          item.validation?.area_difference_percent != null
            ? Number(item.validation.area_difference_percent)
            : item.area_difference_percent != null
              ? Number(item.area_difference_percent)
              : undefined,

        reliability: item.reliability ?? "UNKNOWN",
      }),
    )
    .sort((a, b) => a.year - b.year);
}


/* =========================================================
   APP
========================================================= */

function App() {

  const [theme, setTheme] =
    useState<Theme>("system");


  const [selectedGlacier, setSelectedGlacier] =
    useState<Glacier | null>(null);


  const [glacierGeometry, setGlacierGeometry] =
    useState<GlacierGeometry | null>(
      null,
    );


  const [geometryLoading, setGeometryLoading] =
    useState(false);


  const [geometryError, setGeometryError] =
    useState("");


  const [search, setSearch] =
    useState("");


  const [showResults, setShowResults] =
    useState(false);


  const [searchResults, setSearchResults] =
    useState<Glacier[]>([]);


  const [searchLoading, setSearchLoading] =
    useState(false);


  const [searchError, setSearchError] =
    useState("");


  const [showThemeMenu, setShowThemeMenu] =
    useState(false);


  const [mobileMenu, setMobileMenu] =
    useState(false);


  const [activeSection, setActiveSection] =
    useState("home");


  const [liveAnalysis, setLiveAnalysis] =
    useState<LiveAnalysis | null>(null);


  const [isAnalyzing, setIsAnalyzing] =
    useState(false);


  const [analysisError, setAnalysisError] =
    useState("");


  const [historical, setHistorical] =
    useState<HistoricalPoint[]>([]);

  const [glimsReference, setGlimsReference] =
    useState<GlimsReference | null>(null);


  const [historicalAnalysis, setHistoricalAnalysis] =
    useState<HistoricalAnalysisData | null>(
      null,
    );


  const [changeAnalysis, setChangeAnalysis] =
    useState<ChangeAnalysisData | null>(null);


  const [prediction, setPrediction] =
    useState<PredictionPoint[]>([]);


  const [historyLoading, setHistoryLoading] =
    useState(false);


  const [historyError, setHistoryError] =
    useState("");


  const [historicalRunning, setHistoricalRunning] =
    useState(false);


  /*
   * Monotonically increasing request id.
   * Every glacier selection invalidates all older historical-analysis
   * work so an old glacier can never overwrite the current glacier.
   */
  const historicalRequestIdRef = useRef(0);


  const [reportLoading, setReportLoading] =
    useState(false);


  /* =======================================================
     THEME
  ======================================================= */

  useEffect(() => {

    const saved =
      localStorage.getItem(
        "glacier-theme",
      ) as Theme | null;


    if (saved) {
      setTheme(saved);
    }

  }, []);


  useEffect(() => {

    const root =
      document.documentElement;


    if (theme === "system") {

      root.dataset.theme =
        window.matchMedia(
          "(prefers-color-scheme: dark)",
        ).matches
          ? "dark"
          : "light";

    } else {

      root.dataset.theme =
        theme;

    }


    localStorage.setItem(
      "glacier-theme",
      theme,
    );

  }, [theme]);


  /* =======================================================
     GLOBAL RGI SEARCH
  ======================================================= */

  useEffect(() => {

    const query =
      search.trim();


    if (query.length < 2) {

      setSearchResults([]);
      setSearchLoading(false);
      setSearchError("");

      return;
    }


    const controller =
      new AbortController();


    const searchGlobalRGI =
      async () => {

        try {

          setSearchResults([]);
          setSearchLoading(true);
          setSearchError("");


          const response =
            await fetch(
              `${API}/api/glaciers/search?query=${encodeURIComponent(
                query,
              )}&limit=10`,
              {
                signal:
                  controller.signal,
              },
            );


          const body =
            await response
              .json()
              .catch(
                () => null,
              );


          if (!response.ok) {

            throw new Error(
              typeof body?.detail ===
                "string"
                ? body.detail
                : `Glacier search failed with status ${response.status}`,
            );

          }


          const data =
            body as GlacierSearchResponse;


          const mappedResults:
            Glacier[] =
            data.results.map(
              (item) => ({

                id:
                  item.id,

                name:
                  item.name,

                region:
                  item.region,

                country:
                  item.country,

                latitude:
                  Number(
                    item.latitude,
                  ),

                longitude:
                  Number(
                    item.longitude,
                  ),

                area:
                  item.area_km2 !==
                  null
                    ? Number(
                        item.area_km2,
                      )
                    : null,

                matched_by:
                  item.matched_by,

              }),
            );


          setSearchResults(
            mappedResults,
          );

        } catch (error) {

          if (
            error instanceof
              DOMException &&
            error.name ===
              "AbortError"
          ) {

            return;

          }


          setSearchResults([]);


          setSearchError(
            error instanceof Error
              ? error.message
              : "Could not search the RGI glacier inventory.",
          );

        } finally {

          if (
            !controller.signal
              .aborted
          ) {

            setSearchLoading(
              false,
            );

          }

        }

      };


    const timer =
      window.setTimeout(
        searchGlobalRGI,
        300,
      );


    return () => {

      window.clearTimeout(
        timer,
      );

      controller.abort();

    };

  }, [search]);


  /* =======================================================
     SELECT GLACIER
  ======================================================= */

  const selectGlacier = (
    glacier: Glacier,
  ) => {

    // Invalidate every in-flight analysis for the previously
    // selected glacier before changing the selection.
    historicalRequestIdRef.current += 1;

    setSelectedGlacier(
      glacier,
    );


    setSearch(
      glacier.name,
    );


    setShowResults(
      false,
    );


    setSearchResults(
      [],
    );


    setGlacierGeometry(
      null,
    );


    setGeometryError(
      "",
    );


    setLiveAnalysis(
      null,
    );


    setAnalysisError(
      "",
    );


    setHistorical(
      [],
    );

    setGlimsReference(null);

    setHistoricalAnalysis(
      null,
    );

    setChangeAnalysis(
      null,
    );


    setPrediction(
      [],
    );


    setHistoryError(
      "",
    );

  };


  /* =======================================================
     LOAD SELECTED GLACIER RGI GEOMETRY
  ======================================================= */

  useEffect(() => {

    if (!selectedGlacier) {

      setGlacierGeometry(
        null,
      );

      setGeometryError("");

      return;
    }


    let cancelled = false;


    const loadGlacierGeometry =
      async () => {

        setGeometryLoading(
          true,
        );

        setGeometryError("");

        setGlacierGeometry(
          null,
        );


        try {

          const response =
            await fetch(
              `${API}/api/glaciers/${encodeURIComponent(
                selectedGlacier.id,
              )}`,
            );


          const body =
            await response
              .json()
              .catch(
                () => null,
              );


          if (!response.ok) {

            throw new Error(
              typeof body?.detail ===
                "string"
                ? body.detail
                : `Could not load glacier geometry (${response.status})`,
            );

          }


          const data =
            body as GlacierGeometryResponse;


          if (
            !data.glacier ||
            !data.glacier.geometry
          ) {

            throw new Error(
              "RGI geometry is not available for this glacier.",
            );

          }


          if (!cancelled) {

            setGlacierGeometry(
              data.glacier.geometry,
            );

          }

        } catch (error) {

          if (!cancelled) {

            setGlacierGeometry(
              null,
            );


            setGeometryError(
              error instanceof Error
                ? error.message
                : "Could not load RGI glacier geometry.",
            );

          }

        } finally {

          if (!cancelled) {

            setGeometryLoading(
              false,
            );

          }

        }

      };


    loadGlacierGeometry();


    return () => {

      cancelled = true;

    };

  }, [selectedGlacier]);


  /* =======================================================
     SCROLL
  ======================================================= */

  const scrollTo = (
    id: string,
  ) => {

    setActiveSection(
      id,
    );


    setMobileMenu(
      false,
    );


    if (id === "home") {

      window.scrollTo({
        top: 0,
        behavior: "smooth",
      });

      return;
    }


    document
      .getElementById(id)
      ?.scrollIntoView({
        behavior: "smooth",
      });

  };


  /* =======================================================
     LIVE AI ANALYSIS
  ======================================================= */

  const analyzeGlacier =
    async () => {

      if (!selectedGlacier) {

        setAnalysisError(
          "Please select a glacier first.",
        );

        return;
      }


      setIsAnalyzing(
        true,
      );


      setAnalysisError(
        "",
      );


      setLiveAnalysis(
        null,
      );


      try {

        const params =
          new URLSearchParams({

            name:
              selectedGlacier.name,

            rgi_id:
              selectedGlacier.id,

            latitude:
              String(
                selectedGlacier.latitude,
              ),

            longitude:
              String(
                selectedGlacier.longitude,
              ),

          });


        const response =
          await fetch(
            `${API}/api/live/analyze-live?${params.toString()}`,
          );


        const body =
          await response
            .json()
            .catch(
              () => null,
            );


        if (!response.ok) {

          throw new Error(
            typeof body?.detail ===
              "string"
              ? body.detail
              : `Live analysis failed with status ${response.status}`,
          );

        }


        setLiveAnalysis(
          body as LiveAnalysis,
        );


        setTimeout(() => {

          document
            .getElementById(
              "analysis",
            )
            ?.scrollIntoView({
              behavior:
                "smooth",
            });

        }, 100);


      } catch (error) {

        setAnalysisError(
          error instanceof Error
            ? error.message
            : "Could not connect to GlacierAI backend.",
        );

      } finally {

        setIsAnalyzing(
          false,
        );

      }

    };


  /* =======================================================
     HISTORICAL DATA
  ======================================================= */

  useEffect(() => {

    if (!selectedGlacier) {
      setHistorical([]);
      setGlimsReference(null);
      setHistoricalAnalysis(null);
      setChangeAnalysis(null);
      setPrediction([]);
      setHistoryError("");
      setHistoryLoading(false);
      return;
    }

    // This effect belongs to the current glacier selection.
    // Incrementing the id invalidates any older analysis request.
    const requestId = ++historicalRequestIdRef.current;

    const controller = new AbortController();

    const loadHistorical = async () => {

      const glacierName = selectedGlacier.name;
      const rgiId = selectedGlacier.id;

      // Immediately clear data belonging to the previously selected glacier.
      setHistoryLoading(true);
      setHistoryError("");
      setHistorical([]);
      setHistoricalAnalysis(null);
      setChangeAnalysis(null);
      setPrediction([]);

      try {

        const [
          historyResponse,
          changeResponse,
          predictionResponse,
        ] = await Promise.all([

          fetch(
            `${API}/api/historical?glacier=${encodeURIComponent(
              glacierName,
            )}&rgi_id=${encodeURIComponent(rgiId)}`,
            {
              signal: controller.signal,
            },
          ),

          fetch(
            `${API}/api/historical/change-analysis?glacier=${encodeURIComponent(
              glacierName,
            )}&rgi_id=${encodeURIComponent(rgiId)}`,
            {
              signal: controller.signal,
            },
          ),

          fetch(
            `${API}/api/prediction?glacier=${encodeURIComponent(
              glacierName,
            )}&rgi_id=${encodeURIComponent(rgiId)}`,
            {
              signal: controller.signal,
            },
          ),

        ]);

        if (!historyResponse.ok) {

          if (historyResponse.status === 404) {
            throw new Error(
              `No historical analysis is available for ${glacierName} yet.`,
            );
          }

          throw new Error(
            `Historical API returned ${historyResponse.status}`,
          );
        }

        const historyBody =
          await historyResponse.json();

        const glimsReference =
          historyBody?.glims_reference ??
          historyBody?.data?.glims_reference ??
          null;

        const changeBody =
          changeResponse.ok
            ? await changeResponse.json()
            : null;

        const predictionBody =
          predictionResponse.ok
            ? await predictionResponse.json()
            : null;

        // Ignore results if this request was cancelled because
        // the user selected another glacier.
        if (controller.signal.aborted) {
          return;
        }

        const historicalData =
          historyBody?.data ?? {};

        /*
         * Identity protection:
         * The returned RGI ID must match the currently selected
         * glacier before any historical data is placed in state.
         */
        const returnedRgiId =
          historicalData?.glacier?.rgi_id ??
          historyBody?.rgi_id;

        if (
          returnedRgiId &&
          returnedRgiId !== rgiId
        ) {
          console.warn(
            "GlacierAI: ignoring historical response for wrong RGI ID",
            {
              requested: rgiId,
              returned: returnedRgiId,
            },
          );

          return;
        }

        /*
         * Current backend returns data.records.
         * The fallback to observations/results keeps the
         * frontend compatible with older saved responses too.
         */
        const rawRecords =
          historicalData?.records ??
          historicalData?.observations ??
          historicalData?.results ??
          [];

        const records: HistoricalPoint[] =
          normalizeHistoricalRecords(rawRecords);

        console.log(
          "GlacierAI historical records:",
          {
            glacier: glacierName,
            rgiId,
            records,
          },
        );

        setHistoricalAnalysis(
          Array.isArray(historicalData)
            ? null
            : (historicalData as HistoricalAnalysisData),
        );

        setGlimsReference(
          glimsReference as GlimsReference | null,
        );

        setChangeAnalysis(
          changeBody?.data ?? null,
        );

        setHistorical(records);

        setPrediction(
          normalizePrediction(predictionBody),
        );

      } catch (error) {

        // Abort is expected when the user selects another glacier.
        if (
          error instanceof DOMException &&
          error.name === "AbortError"
        ) {
          return;
        }

        if (!controller.signal.aborted) {
          setHistoryError(
            error instanceof Error
              ? error.message
              : "Historical data could not be loaded.",
          );
        }

      } finally {

        if (!controller.signal.aborted) {
          setHistoryLoading(false);
        }

      }
    };

    loadHistorical();

    // Cancel all requests for the previous glacier.
    return () => {
      controller.abort();
    };

  }, [selectedGlacier]);


  /* =======================================================
     RUN / REFRESH HISTORICAL ANALYSIS
  ======================================================= */

  const runHistoricalAnalysis = async () => {

    if (!selectedGlacier) {
      setHistoryError(
        "Please select a glacier first.",
      );
      return;
    }

    /*
     * Capture the exact glacier and request id at the moment
     * the user starts the analysis.
     */
    const glacierAtStart = selectedGlacier;
    const requestId = ++historicalRequestIdRef.current;
    const controller = new AbortController();

    const isCurrentRequest = () =>
      !controller.signal.aborted &&
      requestId === historicalRequestIdRef.current;

    setHistoricalRunning(true);
    setHistoryError("");

    try {

      const response = await fetch(
        `${API}/api/historical/analyze`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            name: glacierAtStart.name,
            rgi_id: glacierAtStart.id,
            start_year: 2023,
            end_year: 2026,
          }),
          signal: controller.signal,
        },
      );

      if (!isCurrentRequest()) {
        return;
      }

      const body = await response.json().catch(() => null);

      if (!isCurrentRequest()) {
        return;
      }

      if (!response.ok) {
        throw new Error(
          typeof body?.detail === "string"
            ? body.detail
            : `Historical analysis failed with status ${response.status}`,
        );
      }

      /*
       * The POST response already contains the completed
       * historical result. Use it immediately when available.
       */
      const returnedData = body?.data ?? null;

      if (returnedData && isCurrentRequest()) {

        const returnedRgiId =
          returnedData?.glacier?.rgi_id ??
          returnedData?.rgi_id;

        // Never put a response for another glacier into state.
        if (
          returnedRgiId &&
          returnedRgiId !== glacierAtStart.id
        ) {
          console.warn(
            "GlacierAI: ignoring historical POST response for wrong RGI ID",
            {
              requested: glacierAtStart.id,
              returned: returnedRgiId,
            },
          );
          return;
        }

        const rawRecords =
          returnedData.records ??
          returnedData.observations ??
          returnedData.results ??
          [];

        const records: HistoricalPoint[] =
          normalizeHistoricalRecords(rawRecords);

        setHistoricalAnalysis(
          returnedData as HistoricalAnalysisData,
        );

        setGlimsReference(
          returnedData?.glims_reference ?? null,
        );

        setHistorical(records);
      }

      /*
       * Reload persisted historical data so the UI uses exactly
       * what was saved by the backend.
       */
      const historyResponse = await fetch(
        `${API}/api/historical?glacier=${encodeURIComponent(
          glacierAtStart.name,
        )}&rgi_id=${encodeURIComponent(glacierAtStart.id)}`,
        {
          signal: controller.signal,
        },
      );

      if (!isCurrentRequest()) {
        return;
      }

      if (historyResponse.ok) {

        const historyBody =
          await historyResponse.json();

        if (!isCurrentRequest()) {
          return;
        }

        const historicalData =
          historyBody?.data ?? {};

        const refreshedGlimsReference =
          historyBody?.glims_reference ??
          historyBody?.data?.glims_reference ??
          null;

        const returnedRgiId =
          historicalData?.glacier?.rgi_id ??
          historyBody?.rgi_id;

        if (
          returnedRgiId &&
          returnedRgiId !== glacierAtStart.id
        ) {
          console.warn(
            "GlacierAI: ignoring historical GET response for wrong RGI ID",
            {
              requested: glacierAtStart.id,
              returned: returnedRgiId,
            },
          );
          return;
        }

        const rawRecords =
          historicalData?.records ??
          historicalData?.observations ??
          historicalData?.results ??
          [];

        const records: HistoricalPoint[] =
          normalizeHistoricalRecords(rawRecords);

        setHistoricalAnalysis(
          Array.isArray(historicalData)
            ? null
            : (historicalData as HistoricalAnalysisData),
        );

        setGlimsReference(
          refreshedGlimsReference as GlimsReference | null,
        );

        setHistorical(records);
      }

      const changeResponse = await fetch(
        `${API}/api/historical/change-analysis?glacier=${encodeURIComponent(
          glacierAtStart.name,
        )}&rgi_id=${encodeURIComponent(glacierAtStart.id)}`,
        {
          signal: controller.signal,
        },
      );

      if (!isCurrentRequest()) {
        return;
      }

      if (changeResponse.ok) {

        const changeBody =
          await changeResponse.json();

        if (!isCurrentRequest()) {
          return;
        }

        setChangeAnalysis(
          changeBody?.data ?? null,
        );

      } else {
        setChangeAnalysis(null);
      }

      const predictionResponse = await fetch(
        `${API}/api/prediction?glacier=${encodeURIComponent(
          glacierAtStart.name,
        )}&rgi_id=${encodeURIComponent(glacierAtStart.id)}`,
        {
          signal: controller.signal,
        },
      );

      if (!isCurrentRequest()) {
        return;
      }

      if (predictionResponse.ok) {

        const predictionBody =
          await predictionResponse.json();

        if (!isCurrentRequest()) {
          return;
        }

        setPrediction(
          normalizePrediction(predictionBody),
        );

      } else {
        setPrediction([]);
      }

      setHistoryError("");

    } catch (error) {

      if (
        error instanceof DOMException &&
        error.name === "AbortError"
      ) {
        return;
      }

      if (isCurrentRequest()) {
        setHistoryError(
          error instanceof Error
            ? error.message
            : "Historical analysis could not be completed.",
        );
      }

    } finally {

      /*
       * Only the active request is allowed to change loading state.
       * A previous glacier's request cannot turn off the spinner
       * for the current glacier.
       */
      if (isCurrentRequest()) {
        setHistoricalRunning(false);
        setHistoryLoading(false);
      }

    }
  };

  /* =======================================================
     REPORT
  ======================================================= */

  const escapeReportHtml = (value: unknown) =>
    String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");


  const reportImageUrl = (path?: string | null) => {
    if (!path) {
      return "";
    }

    return path.startsWith("http")
      ? path
      : `${API}${path}`;
  };


  const buildReportHtml = (predictionOverride?: PredictionPoint[]) => {
    if (!selectedGlacier) {
      return "";
    }

    const fmt = (value: unknown, digits = 4, suffix = "") => {
      const n = Number(value);
      return Number.isFinite(n) ? `${n.toFixed(digits)}${suffix}` : "Not available";
    };

    const safe = (value: unknown, fallback = "Not available") => {
      const text = String(value ?? "").trim();
      return text ? escapeReportHtml(text) : fallback;
    };

    const historicalSorted = [...historical]
      .filter((p) => Number.isFinite(Number(p.area_km2)) && p.year != null)
      .sort((a, b) => Number(a.year) - Number(b.year));

    const predictionSource = predictionOverride ?? prediction;

    const predictionSorted = [...predictionSource]
      .filter((p) => Number.isFinite(Number(p.predicted_area_km2 ?? p.area_km2 ?? p.predicted)) && p.year != null)
      .sort((a, b) => Number(a.year) - Number(b.year));

    const glimsRecords = [...(glimsReference?.historical_records ?? [])]
      .filter((r) => Number.isFinite(Number(r.area_km2)) && r.year != null)
      .sort((a, b) => Number(a.year) - Number(b.year));

    const historyRows = historicalSorted
      .map(
        (p) =>
          `<tr>
            <td>${safe(p.year)}</td>
            <td>${safe(p.date)}</td>
            <td>${fmt(p.area_km2, 6)} km²</td>
            <td>${p.coverage_percent != null ? fmt(p.coverage_percent, 2, "%") : "Not available"}</td>
          </tr>`,
      )
      .join("");

    const predictionRows = predictionSorted
      .map(
        (p) =>
          `<tr>
            <td>${safe(p.year)}</td>
            <td>${fmt(p.predicted_area_km2 ?? p.area_km2 ?? p.predicted, 6)} km²</td>
            <td>Trend estimate</td>
          </tr>`,
      )
      .join("");

    const glimsRows = glimsRecords
      .map(
        (r) =>
          `<tr>
            <td>${safe(r.year)}</td>
            <td>${safe(r.date)}</td>
            <td>${fmt(r.area_km2, 6)} km²</td>
            <td>${safe(r.source)}</td>
            <td>${safe(r.status)}</td>
          </tr>`,
      )
      .join("");

    const spatialRows = (changeAnalysis?.spatial_boundary_change ?? [])
      .map(
        (c) =>
          `<tr>
            <td>${safe(c.from_year)} → ${safe(c.to_year)}</td>
            <td>${c.lost_area_km2 != null ? fmt(c.lost_area_km2, 6) + " km²" : "Not available"}</td>
            <td>${c.gained_area_km2 != null ? fmt(c.gained_area_km2, 6) + " km²" : "Not available"}</td>
            <td>${c.spatial_iou != null ? fmt(c.spatial_iou, 4) : "Not available"}</td>
            <td>${safe(c.note ?? c.reason)}</td>
          </tr>`,
      )
      .join("");

    const changeRows = (changeAnalysis?.year_to_year_area_change ?? [])
      .map(
        (c) =>
          `<tr>
            <td>${safe(c.from_year)} → ${safe(c.to_year)}</td>
            <td>${fmt(c.from_area_km2, 6)} km²</td>
            <td>${fmt(c.to_area_km2, 6)} km²</td>
            <td>${fmt(c.area_change_km2, 6)} km²</td>
            <td>${c.percentage_change != null ? fmt(c.percentage_change, 2, "%") : "Not available"}</td>
            <td>${safe(c.change_interpretation)}</td>
          </tr>`,
      )
      .join("");

    const inventoryArea =
      selectedGlacier.area != null
        ? `${selectedGlacier.area.toFixed(4)} km²`
        : "Not available";

    /* -------------------------------------------------------
       INLINE SVG LINE CHARTS
       These are embedded directly into the report so they
       work in View Report and in the downloaded HTML file.
    ------------------------------------------------------- */
    const makeLineChart = (
      title: string,
      points: Array<{ label: string; value: number }>,
      lineColor: string,
      dashed = false,
    ) => {
      if (points.length < 2) {
        return `<div class="chart-empty"><b>${escapeReportHtml(title)}</b><span>Not enough processed observations to draw this graph.</span></div>`;
      }

      const width = 960;
      const height = 380;
      const left = 72;
      const right = 30;
      const top = 58;
      const bottom = 62;
      const plotW = width - left - right;
      const plotH = height - top - bottom;
      const values = points.map((p) => p.value);
      const minValue = Math.min(...values);
      const maxValue = Math.max(...values);
      const range = Math.max(maxValue - minValue, 1);
      const pad = range * 0.12;
      const yMin = Math.max(0, minValue - pad);
      const yMax = maxValue + pad;

      const x = (i: number) =>
        left + (points.length === 1 ? plotW / 2 : (i / (points.length - 1)) * plotW);
      const y = (v: number) =>
        top + ((yMax - v) / (yMax - yMin)) * plotH;

      const path = points
        .map((p, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(p.value).toFixed(1)}`)
        .join(" ");

      const grid = [0, 1, 2, 3, 4].map((i) => {
        const value = yMax - ((yMax - yMin) * i) / 4;
        const yy = y(value);
        return `
          <line x1="${left}" y1="${yy}" x2="${width - right}" y2="${yy}" stroke="#dbe7ee" stroke-width="1"/>
          <text x="${left - 12}" y="${yy + 5}" text-anchor="end" font-size="12" fill="#61758a">${value.toFixed(1)}</text>
        `;
      }).join("");

      const labels = points.map((p, i) => `
        <text x="${x(i)}" y="${height - 26}" text-anchor="middle" font-size="12" fill="#61758a">${escapeReportHtml(p.label)}</text>
        <circle cx="${x(i)}" cy="${y(p.value)}" r="5" fill="${lineColor}"/>
        <text x="${x(i)}" y="${y(p.value) - 12}" text-anchor="middle" font-size="11" font-weight="700" fill="#123b56">${p.value.toFixed(3)}</text>
      `).join("");

      return `
        <div class="chart-card">
          <div class="chart-title">${escapeReportHtml(title)}</div>
          <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeReportHtml(title)}" class="report-chart">
            <rect x="0" y="0" width="${width}" height="${height}" rx="12" fill="#fbfdff"/>
            ${grid}
            <line x1="${left}" y1="${top}" x2="${left}" y2="${height - bottom}" stroke="#9db3c2" stroke-width="1.2"/>
            <line x1="${left}" y1="${height - bottom}" x2="${width - right}" y2="${height - bottom}" stroke="#9db3c2" stroke-width="1.2"/>
            <path d="${path}" fill="none" stroke="${lineColor}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" ${dashed ? 'stroke-dasharray="10 8"' : ""}/>
            ${labels}
          </svg>
          <div class="chart-caption">Area in km². Values are taken directly from the processed observations shown in this report.</div>
        </div>
      `;
    };

    const glimsChart = makeLineChart(
      `${selectedGlacier.name} — GLIMS historical reference`,
      glimsRecords.map((r) => ({ label: String(r.year), value: Number(r.area_km2) })),
      "#58bdb0",
    );

    const combinedChart = makeLineChart(
      `${selectedGlacier.name} — historical and future area estimates`,
      [
        ...historicalSorted.map((p) => ({ label: String(p.year), value: Number(p.area_km2) })),
        ...predictionSorted.map((p) => ({ label: String(p.year), value: Number(p.predicted_area_km2 ?? p.area_km2 ?? p.predicted) })),
      ],
      "#0f7c86",
    );

    const live = liveAnalysis;
    const xai = live?.analysis?.xai;

    const liveImages = live
      ? `
        <div class="image-grid">
          ${live.outputs.overlay ? `<figure><img src="${reportImageUrl(live.outputs.overlay)}"><figcaption>AI Segmentation Overlay</figcaption></figure>` : `<figure><div class="missing-media">Not available</div><figcaption>AI Segmentation Overlay</figcaption></figure>`}
          ${live.outputs.mask_png ? `<figure><img src="${reportImageUrl(live.outputs.mask_png)}"><figcaption>Glacier Mask</figcaption></figure>` : `<figure><div class="missing-media">Not available</div><figcaption>Glacier Mask</figcaption></figure>`}
          ${live.outputs.probability_heatmap ? `<figure><img src="${reportImageUrl(live.outputs.probability_heatmap)}"><figcaption>Probability Heatmap</figcaption></figure>` : `<figure><div class="missing-media">Not available</div><figcaption>Probability Heatmap</figcaption></figure>`}
        </div>
      `
      : `<div class="not-available">No live AI analysis was run for this report.</div>`;

    const liveBlock = live
      ? `
        <h2>Latest AI Analysis</h2>
        <div class="cards">
          <div><b>Satellite</b><span>${safe(live.satellite.source)}</span></div>
          <div><b>Observation date</b><span>${safe(live.satellite.observation_date)}</span></div>
          <div><b>Model</b><span>${safe(live.model.name)}</span></div>
          <div><b>Checkpoint</b><span>${safe(live.model.checkpoint)}</span></div>
          <div><b>Glacier pixels</b><span>${Number(live.analysis.glacier_pixels).toLocaleString()}</span></div>
          <div><b>Coverage</b><span>${fmt(live.analysis.coverage_percent, 2, "%")}</span></div>
          <div><b>Estimated area</b><span>${fmt(live.analysis.area_km2, 4)} km²</span></div>
          <div><b>RGI polygon</b><span>${live.analysis.rgi_polygon_applied ? "Applied" : "Not applied"}</span></div>
          <div><b>Resolution</b><span>${safe(live.satellite.resolution_m)} m</span></div>
          <div><b>CRS</b><span>${safe(live.satellite.crs)}</span></div>
          <div><b>Cloud limit</b><span>${fmt(live.satellite.cloud_limit_percent, 0, "%")}</span></div>
          <div><b>Scene ID</b><span>${safe(live.satellite.scene_id)}</span></div>
        </div>
        ${liveImages}
        ${
          xai
            ? `
              <h3>Explainable AI & Uncertainty</h3>
              <div class="cards">
                <div><b>Mean probability</b><span>${fmt(xai.mean_probability, 4)}</span></div>
                <div><b>Minimum probability</b><span>${fmt(xai.minimum_probability, 4)}</span></div>
                <div><b>Maximum probability</b><span>${fmt(xai.maximum_probability, 4)}</span></div>
                <div><b>Threshold</b><span>${fmt(xai.threshold, 2)}</span></div>
                <div><b>Low confidence</b><span>${fmt(xai.confidence_distribution_percent.low, 2, "%")}</span></div>
                <div><b>Uncertain</b><span>${fmt(xai.confidence_distribution_percent.uncertain, 2, "%")}</span></div>
                <div><b>Moderate confidence</b><span>${fmt(xai.confidence_distribution_percent.moderate, 2, "%")}</span></div>
                <div><b>High confidence</b><span>${fmt(xai.confidence_distribution_percent.high, 2, "%")}</span></div>
              </div>
              <p class="note"><b>Explanation:</b> ${safe(xai.explanation)}</p>
            `
            : `<div class="not-available">Explainable AI statistics are not available for this observation.</div>`
        }
      `
      : `<div class="not-available">No live AI analysis was run for this report.</div>`;

    const overall = changeAnalysis?.overall_trend;
    const derivedStart = historicalSorted[0];
    const derivedEnd = historicalSorted[historicalSorted.length - 1];
    const derivedChange =
      derivedStart && derivedEnd
        ? Number(derivedEnd.area_km2) - Number(derivedStart.area_km2)
        : null;
    const derivedYears =
      derivedStart && derivedEnd
        ? Number(derivedEnd.year) - Number(derivedStart.year)
        : 0;
    const derivedAnnual =
      derivedChange != null && derivedYears > 0
        ? derivedChange / derivedYears
        : null;

    const changeSummary = `
      <h2>Area & Spatial Change Summary</h2>
      <div class="cards">
        <div><b>Processed U-Net observations</b><span>${historicalSorted.length}</span></div>
        <div><b>Validation status</b><span>${overall?.trend ? safe(overall.trend) : "Not independently validated"}</span></div>
        <div><b>Start area</b><span>${overall?.start_area_km2 != null ? fmt(overall.start_area_km2) + " km²" : derivedStart ? fmt(derivedStart.area_km2) + " km²" : "Not available"}</span></div>
        <div><b>End area</b><span>${overall?.end_area_km2 != null ? fmt(overall.end_area_km2) + " km²" : derivedEnd ? fmt(derivedEnd.area_km2) + " km²" : "Not available"}</span></div>
        <div><b>Observed area difference</b><span>${overall?.area_change_km2 != null ? fmt(overall.area_change_km2) + " km²" : derivedChange != null ? fmt(derivedChange) + " km²" : "Not available"}</span></div>
        <div><b>Annualized area difference</b><span>${overall?.annualized_area_change_km2_per_year != null ? fmt(overall.annualized_area_change_km2_per_year) + " km²/year" : derivedAnnual != null ? fmt(derivedAnnual) + " km²/year" : "Not available"}</span></div>
        <div><b>Physical retreat rate</b><span>${overall?.retreat_rate_m_per_year != null ? fmt(overall.retreat_rate_m_per_year, 2, " m/year") : "Not reported — boundary validation required"}</span></div>
        <div><b>Assessment</b><span>${overall?.trend ? safe(overall.trend) : "Area change shown; physical retreat not independently validated"}</span></div>
      </div>
      ${changeRows ? `<h3>Year-to-Year Area Change</h3><table><tr><th>Period</th><th>From area</th><th>To area</th><th>Change</th><th>Change %</th><th>Interpretation</th></tr>${changeRows}</table>` : `<div class="not-available">No year-to-year change records were returned.</div>`}
      ${spatialRows ? `<h3>Spatial Mask Change</h3><table><tr><th>Period</th><th>Lost area</th><th>Gained area</th><th>Mask IoU</th><th>Note</th></tr>${spatialRows}</table>` : `<div class="not-available">No spatial mask-change records were returned.</div>`}
      ${changeAnalysis?.scientific_note ? `<p class="note">${safe(changeAnalysis.scientific_note)}</p>` : ""}
    `;

    const glimsBlock = glimsRecords.length
      ? `
        <h2>GLIMS Historical Reference</h2>
        <div class="meta">
          <p><b>GLIMS ID:</b> ${safe(glimsReference?.glims_id)}</p>
          <p><b>Reference records:</b> ${glimsRecords.length}</p>
          <p><b>Layer:</b> ${safe(glimsReference?.glims_layer)}</p>
        </div>
        ${glimsChart}
        <table>
          <tr><th>Year</th><th>Observation date</th><th>GLIMS area</th><th>Source</th><th>Status</th></tr>
          ${glimsRows}
        </table>
        <p class="note">GLIMS records are independent historical reference observations. They are not merged with U-Net observations because dates, sources and delineation methods can differ.</p>
      `
      : `<div class="not-available">No GLIMS historical reference records are available for this glacier.</div>`;

    return `
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GlacierAI Report - ${safe(selectedGlacier.name)}</title>
<style>
body{font-family:Arial,sans-serif;max-width:1100px;margin:0 auto;padding:35px 28px;color:#10243b;line-height:1.55;background:#fff}
h1{color:#075985;margin-bottom:6px}h2{margin-top:34px;border-bottom:1px solid #d8e4ef;padding-bottom:8px;color:#123b56}h3{margin-top:24px;color:#17677d}
table{width:100%;border-collapse:collapse;margin:14px 0 20px;font-size:14px}th,td{border:1px solid #d8e4ef;padding:9px;text-align:left;vertical-align:top}th{background:#eef7fc}
.meta{background:#f4f9fc;padding:18px;border-radius:12px;margin:15px 0}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:15px 0}.cards>div{border:1px solid #d8e4ef;border-radius:10px;padding:12px;background:#fbfdff;min-height:52px}.cards b{display:block;font-size:12px;color:#61758a;margin-bottom:4px}.cards span{font-weight:700;overflow-wrap:anywhere}
.image-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:18px 0}.image-grid figure{margin:0;border:1px solid #d8e4ef;border-radius:10px;padding:8px;background:#fbfdff}.image-grid img{display:block;width:100%;max-height:320px;object-fit:contain;background:#111;border-radius:7px}.image-grid figcaption{text-align:center;font-weight:700;padding:8px 3px;font-size:13px}.missing-media,.not-available{border:1px dashed #b8cad6;border-radius:10px;background:#f7fafc;padding:18px;color:#61758a;text-align:center;margin:12px 0}
.chart-card{border:1px solid #d8e4ef;border-radius:12px;padding:14px;background:#fbfdff;margin:18px 0}.chart-title{font-weight:700;color:#123b56;font-size:16px;margin-bottom:8px}.report-chart{display:block;width:100%;height:auto}.chart-caption{font-size:12px;color:#61758a;margin-top:5px}
.note{font-size:13px;color:#61758a}.footer{margin-top:40px;padding-top:18px;border-top:1px solid #d8e4ef;font-size:12px;color:#61758a}
@media(max-width:800px){.cards,.image-grid{grid-template-columns:1fr}.image-grid img{max-height:none}}
@media print{body{max-width:none;padding:10px}.image-grid img{max-height:260px}.cards{grid-template-columns:repeat(3,1fr)}.chart-card{break-inside:avoid}}
</style>
</head>
<body>
<h1>GlacierAI Monitoring Report</h1>
<p><b>AI-Based Glacier Monitoring & Retreat Analysis</b></p>
<div class="meta">
<p><b>Glacier:</b> ${safe(selectedGlacier.name)}</p>
<p><b>Region:</b> ${safe(selectedGlacier.region)}, ${safe(selectedGlacier.country)}</p>
<p><b>Coordinates:</b> ${fmt(selectedGlacier.latitude, 5)}, ${fmt(selectedGlacier.longitude, 5)}</p>
<p><b>RGI Inventory area:</b> ${inventoryArea}</p>
<p><b>RGI ID:</b> ${safe(selectedGlacier.id)}</p>
</div>

${liveBlock}

<h2>Area History & Future Projection</h2>
${combinedChart}

<h2>Historical Area Observations</h2>
${historicalSorted.length ? `<table><tr><th>Year</th><th>Date</th><th>U-Net V3 estimated area</th><th>Coverage</th></tr>${historyRows}</table>` : `<div class="not-available">No historical U-Net observations have been processed for this glacier.</div>`}

${glimsBlock}

${changeSummary}

<h2>Future Area Estimates</h2>
${predictionSorted.length ? `<table><tr><th>Year</th><th>Predicted area</th><th>Estimate type</th></tr>${predictionRows}</table>` : `<div class="not-available">No future trend estimate is available for this glacier.</div>`}

<p class="note">Historical values are U-Net V3 model estimates. GLIMS values are independent reference observations. Future values are trend-based estimates and are not definitive physical climate predictions. A physical terminus retreat rate is not reported unless boundary geometry supports that measurement.</p>
<div class="footer">Generated by GlacierAI for ${safe(selectedGlacier.name)}.</div>
</body>
</html>`;
  };

  const fetchFreshPredictionForReport = async (): Promise<PredictionPoint[]> => {
    if (!selectedGlacier) {
      return prediction;
    }

    try {
      const response = await fetch(
        `${API}/api/prediction?glacier=${encodeURIComponent(
          selectedGlacier.name,
        )}&rgi_id=${encodeURIComponent(selectedGlacier.id)}`,
      );

      if (!response.ok) {
        return prediction;
      }

      const body = await response.json();
      const fresh = normalizePrediction(body);

      return fresh.length ? fresh : prediction;
    } catch {
      return prediction;
    }
  };


  const viewReport = async () => {
    if (!selectedGlacier) {
      return;
    }

    // Open immediately so Chrome does not block the report as a popup.
    const reportWindow = window.open("", "_blank");

    if (!reportWindow) {
      window.alert("Please allow pop-ups for GlacierAI to view the report.");
      return;
    }

    reportWindow.document.write("<p style=\"font-family:Arial;padding:30px\">Preparing GlacierAI report…</p>");

    const freshPrediction = await fetchFreshPredictionForReport();
    const html = buildReportHtml(freshPrediction);

    reportWindow.document.open();
    reportWindow.document.write(html);
    reportWindow.document.close();
  };


  const generateReport = async () => {
    if (!selectedGlacier) {
      return;
    }

    setReportLoading(true);

    try {
      // Always refresh prediction before building the downloadable report.
      const freshPrediction = await fetchFreshPredictionForReport();
      const html = buildReportHtml(freshPrediction);
      const blob = new Blob([html], { type: "text/html;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");

      anchor.href = url;
      anchor.download = `${selectedGlacier.name.replace(/[^a-z0-9]+/gi, "_")}_GlacierAI_Report.html`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } finally {
      setReportLoading(false);
    }
  };


  /* =======================================================
     RENDER
  ======================================================= */

  return (

    <div className="app">


      {/* =================================================
          HEADER
      ================================================= */}

      <header className="header">

        <button
          className="brand"
          onClick={() =>
            scrollTo("home")
          }
        >

          <div className="brand-icon">

            <Snowflake
              size={21}
            />

          </div>


          <div>

            <div className="brand-name">
              GlacierAI
            </div>

            <div className="brand-subtitle">
              AI-Based Glacier Monitoring
            </div>

          </div>

        </button>


        <nav
          className={
            mobileMenu
              ? "nav nav-open"
              : "nav"
          }
        >

          <button
            onClick={() =>
              scrollTo("home")
            }
            className={
              activeSection ===
              "home"
                ? "active"
                : ""
            }
          >
            Home
          </button>


          <button
            onClick={() =>
              scrollTo("map")
            }
          >
            Global Map
          </button>


          <button
            onClick={() =>
              scrollTo("satellite")
            }
          >
            Satellite
          </button>


          <button
            onClick={() =>
              scrollTo("analysis")
            }
          >
            AI Analysis
          </button>


          <button
            onClick={() =>
              scrollTo("history")
            }
          >
            History
          </button>


          <button
            onClick={() =>
              scrollTo("reports")
            }
          >
            Reports
          </button>

        </nav>


        <div className="header-actions">

          <div className="theme-wrapper">

            <button
              className="icon-button"
              type="button"
              aria-label="Choose colour theme"
              title="Choose colour theme"
              onClick={() =>
                setShowThemeMenu(
                  (v) => !v,
                )
              }
            >

              {theme ===
              "dark" ? (
                <Moon
                  size={17}
                />
              ) : theme ===
                "light" ? (
                <Sun
                  size={17}
                />
              ) : (
                <Settings
                  size={17}
                />
              )}

            </button>


            {showThemeMenu && (

              <div className="theme-menu">

                <button
                  onClick={() => {

                    setTheme(
                      "light",
                    );

                    setShowThemeMenu(
                      false,
                    );

                  }}
                >
                  <Sun
                    size={15}
                  />
                  Light
                </button>


                <button
                  onClick={() => {

                    setTheme(
                      "dark",
                    );

                    setShowThemeMenu(
                      false,
                    );

                  }}
                >
                  <Moon
                    size={15}
                  />
                  Dark
                </button>


                <button
                  onClick={() => {

                    setTheme(
                      "system",
                    );

                    setShowThemeMenu(
                      false,
                    );

                  }}
                >
                  <Settings
                    size={15}
                  />
                  System
                </button>

              </div>

            )}

          </div>


          <button
            className="menu-button"
            type="button"
            aria-label={
              mobileMenu
                ? "Close navigation menu"
                : "Open navigation menu"
            }
            title={
              mobileMenu
                ? "Close navigation menu"
                : "Open navigation menu"
            }
            onClick={() =>
              setMobileMenu(
                (v) => !v,
              )
            }
          >

            {mobileMenu ? (
              <X
                size={18}
              />
            ) : (
              <Menu
                size={18}
              />
            )}

          </button>

        </div>

      </header>


      <main>


        {/* =================================================
            HERO
        ================================================= */}

        <section
          className="hero-section"
          id="home"
        >

          <div className="hero-content">


            <div className="status-pill">

              <span className="status-dot" />

              AI Glacier Monitoring Platform

            </div>


            <h1>

              Monitor the{" "}

              <span>
                Frozen Earth.
              </span>

            </h1>


            <p className="hero-description">

              GlacierAI combines
              Sentinel-2 satellite
              imagery, RGI 7.0
              glacier inventory data
              and U-Net V3 segmentation
              to monitor glacier
              boundaries and estimate
              glacier-area change.

            </p>


            {/* GLOBAL SEARCH */}

            <div className="search-container">

              <Search
                size={18}
              />


              <input
                value={search}
                aria-label="Search the global glacier inventory"

                onKeyDown={(e) => {

                  if (
                    e.key !==
                    "Enter"
                  ) {
                    return;
                  }


                  e.preventDefault();


                  if (
                    !searchLoading &&
                    searchResults.length >
                      0 &&
                    search.trim()
                      .length >=
                      2
                  ) {

                    selectGlacier(
                      searchResults[0],
                    );

                  }

                }}


                onChange={(e) => {

                  const value =
                    e.target.value;


                  setSearch(
                    value,
                  );


                  setShowResults(
                    true,
                  );


                  setSearchResults(
                    [],
                  );


                  setSearchError("");

                }}


                onFocus={() =>
                  setShowResults(
                    true,
                  )
                }


                placeholder="Search any glacier worldwide..."
              />


              {search && (

                <button
                  className="icon-button"
                  type="button"
                  aria-label="Clear glacier search"
                  title="Clear search"

                  onClick={() => {

                    setSearch("");

                    setShowResults(
                      false,
                    );

                    setSearchResults(
                      [],
                    );

                  }}
                >

                  <X
                    size={15}
                  />

                </button>

              )}


              <button
                className="search-button"

                onClick={() => {

                  if (
                    !searchLoading &&
                    searchResults.length >
                      0
                  ) {

                    selectGlacier(
                      searchResults[0],
                    );

                  }

                }}

                disabled={
                  searchLoading ||
                  searchResults.length ===
                    0
                }
              >

                {searchLoading
                  ? "Searching…"
                  : "Search"}

              </button>


              {/* SEARCH RESULTS */}

              {showResults &&
                search.trim()
                  .length >=
                  2 && (

                  <div className="search-results">

                    {searchLoading && (

                      <div className="search-result">

                        <div className="result-icon">

                          <Search
                            size={16}
                          />

                        </div>


                        <div>

                          <strong>
                            Searching RGI 7.0...
                          </strong>

                          <span>
                            Searching the global
                            glacier inventory
                          </span>

                        </div>

                      </div>

                    )}


                    {!searchLoading &&
                      searchResults.map(
                        (
                          glacier,
                        ) => (

                          <button
                            key={
                              glacier.id
                            }
                            className="search-result"

                            onClick={() =>
                              selectGlacier(
                                glacier,
                              )
                            }
                          >

                            <div className="result-icon">

                              <Mountain
                                size={16}
                              />

                            </div>


                            <div>

                              <strong>
                                {
                                  glacier.name
                                }
                              </strong>


                              <span>

                                {glacier.latitude.toFixed(
                                  4,
                                )}

                                ,{" "}

                                {glacier.longitude.toFixed(
                                  4,
                                )}

                                {glacier.area !==
                                  null &&
                                  ` · ${glacier.area.toFixed(
                                    2,
                                  )} km²`}

                              </span>

                            </div>


                            <ChevronRight
                              size={15}
                            />

                          </button>

                        ),
                      )}


                    {!searchLoading &&
                      searchResults.length ===
                        0 &&
                      !searchError && (

                        <div className="search-result">

                          <div className="result-icon">

                            <Mountain
                              size={16}
                            />

                          </div>


                          <div>

                            <strong>
                              No glacier found
                            </strong>

                            <span>
                              Try a glacier name
                              or RGI ID
                            </span>

                          </div>

                        </div>

                    )}


                    {searchError && (

                      <div className="search-result">

                        <div>

                          <strong>
                            Search failed
                          </strong>

                          <span>
                            {
                              searchError
                            }
                          </span>

                        </div>

                      </div>

                    )}

                  </div>

                )}

            </div>


            <div
              className="search-hint"
              aria-live="polite"
            >

              <span>
                Tip
              </span>{" "}

              Type at least 2 characters,
              then choose a glacier from
              the results.

            </div>


            <div className="hero-actions">

              <button
                className="primary-button"
                onClick={() =>
                  scrollTo("map")
                }
              >

                <Globe2
                  size={16}
                />

                Explore Global Map

              </button>


              <button
                className="secondary-button"
                onClick={() =>
                  scrollTo("analysis")
                }
              >

                View AI Analysis

                <ArrowRight
                  size={15}
                />

              </button>

            </div>

          </div>

        </section>


        {/* =================================================
            SELECTED GLACIER
        ================================================= */}

        {selectedGlacier && (

          <section
            className="selected-section"
          >

            <div className="selected-card">

              <div>

                <div className="eyebrow">
                  SELECTED GLACIER
                </div>


                <h2>
                  {selectedGlacier.name}
                </h2>


                <p>
                  {selectedGlacier.region}
                  {" · "}
                  {selectedGlacier.country}
                </p>


                <div className="selection-status">

                  <span className="status-dot" />

                  Ready for analysis

                </div>


                <div className="glacier-meta">

                  <span>

                    <Globe2
                      size={13}
                    />

                    {selectedGlacier.latitude.toFixed(
                      4,
                    )}
                    ,{" "}
                    {selectedGlacier.longitude.toFixed(
                      4,
                    )}

                  </span>


                  <span>

                    <Layers3
                      size={13}
                    />

                    {selectedGlacier.area !==
                    null
                      ? `${selectedGlacier.area.toFixed(
                          2,
                        )} km² inventory`
                      : "Area unavailable"}

                  </span>


                  <span>

                    <Database
                      size={13}
                    />

                    RGI 7.0

                  </span>

                </div>

              </div>


              <button
                className="outline-button"
                onClick={() =>
                  scrollTo(
                    "analysis",
                  )
                }
              >

                Analyse Glacier

                <ArrowRight
                  size={15}
                />

              </button>

            </div>

          </section>

        )}


        {/* =================================================
            GLOBAL MAP
        ================================================= */}

        <section
          className="section"
          id="map"
        >

          <div className="section-heading">

            <div>

              <div className="eyebrow">
                GLOBAL INVENTORY
              </div>


              <h2>
                Explore Glacier Locations
              </h2>


              <p>

                Search the global RGI 7.0
                inventory to select any glacier
                worldwide. Only the currently
                selected glacier is displayed
                on the map.

              </p>

            </div>


            <div className="map-status">

              <span className="status-dot" />

              Global RGI 7.0 · Worldwide
              glacier search

            </div>

          </div>


          {geometryLoading &&
            selectedGlacier && (

              <div className="map-status">

                <span className="status-dot" />

                Loading RGI glacier boundary…

              </div>

            )}


          {geometryError && (

            <div className="analysis-error">
              {geometryError}
            </div>

          )}


          <div className="map-card">

            <MapContainer
              center={[
                25,
                20,
              ]}
              zoom={2}
              minZoom={2}
              maxZoom={16}
              scrollWheelZoom
              className="glacier-map"
            >

              <TileLayer
                attribution="&copy; OpenStreetMap contributors"
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />


              {selectedGlacier && (

                <RecenterMap
                  latitude={
                    selectedGlacier.latitude
                  }

                  longitude={
                    selectedGlacier.longitude
                  }

                  geometry={
                    glacierGeometry
                  }
                />

              )}


              {/* =================================================
                  RGI POLYGON
              ================================================= */}

              {selectedGlacier &&
                glacierGeometry &&
                glacierGeometry.type ===
                  "Polygon" && (

                  <Polygon
                    positions={polygonToLeafletPositions(
                      glacierGeometry.coordinates,
                    )}

                    pathOptions={{
                      color:
                        "#075985",

                      weight: 3,

                      fillColor:
                        "#55b8ff",

                      fillOpacity:
                        0.35,
                    }}
                  >

                    <Popup>

                      <strong>
                        {
                          selectedGlacier.name
                        }
                      </strong>

                      <br />

                      {
                        selectedGlacier.region
                      }
                      ,{" "}
                      {
                        selectedGlacier.country
                      }

                      <br />
                      <br />

                      <span>

                        RGI ID:{" "}
                        {
                          selectedGlacier.id
                        }

                      </span>

                      <br />

                      <span>

                        Coordinates:{" "}
                        {
                          selectedGlacier.latitude.toFixed(
                            5,
                          )
                        }
                        ,{" "}
                        {
                          selectedGlacier.longitude.toFixed(
                            5,
                          )
                        }

                      </span>

                      <br />

                      <span>

                        RGI area:{" "}
                        {
                          selectedGlacier.area !==
                          null
                            ? `${selectedGlacier.area.toFixed(
                                4,
                              )} km²`
                            : "Unavailable"
                        }

                      </span>

                      <br />
                      <br />

                      <button
                        className="popup-button"

                        onClick={() =>
                          scrollTo(
                            "analysis",
                          )
                        }
                      >

                        Analyse Glacier

                      </button>

                    </Popup>

                  </Polygon>

                )}


              {/* =================================================
                  RGI MULTI-POLYGON
              ================================================= */}

              {selectedGlacier &&
                glacierGeometry &&
                glacierGeometry.type ===
                  "MultiPolygon" && (

                  <>
                    {multiPolygonToLeafletPositions(
                      glacierGeometry.coordinates,
                    ).map(
                      (
                        polygon,
                        index,
                      ) => (

                        <Polygon
                          key={
                            `glacier-polygon-${index}`
                          }

                          positions={
                            polygon
                          }

                          pathOptions={{
                            color:
                              "#075985",

                            weight: 3,

                            fillColor:
                              "#55b8ff",

                            fillOpacity:
                              0.35,
                          }}
                        >

                          <Popup>

                            <strong>
                              {
                                selectedGlacier.name
                              }
                            </strong>

                            <br />

                            {
                              selectedGlacier.region
                            }
                            ,{" "}
                            {
                              selectedGlacier.country
                            }

                            <br />
                            <br />

                            <span>

                              RGI ID:{" "}
                              {
                                selectedGlacier.id
                              }

                            </span>

                            <br />

                            <span>

                              Coordinates:{" "}
                              {
                                selectedGlacier.latitude.toFixed(
                                  5,
                                )
                              }
                              ,{" "}
                              {
                                selectedGlacier.longitude.toFixed(
                                  5,
                                )
                              }

                            </span>

                            <br />

                            <span>

                              RGI area:{" "}
                              {
                                selectedGlacier.area !==
                                null
                                  ? `${selectedGlacier.area.toFixed(
                                      4,
                                    )} km²`
                                  : "Unavailable"
                              }

                            </span>

                            <br />
                            <br />

                            <button
                              className="popup-button"

                              onClick={() =>
                                scrollTo(
                                  "analysis",
                                )
                              }
                            >

                              Analyse Glacier

                            </button>

                          </Popup>

                        </Polygon>

                      ),
                    )}
                  </>

                )}


              {/* =================================================
                  FALLBACK MARKER
              ================================================= */}

              {selectedGlacier &&
                !glacierGeometry && (

                  <CircleMarker
                    center={[
                      selectedGlacier.latitude,
                      selectedGlacier.longitude,
                    ]}

                    radius={10}

                    pathOptions={{
                      color:
                        "#075985",

                      fillColor:
                        "#55b8ff",

                      fillOpacity:
                        0.9,

                      weight: 3,
                    }}
                  >

                    <Popup>

                      <strong>
                        {
                          selectedGlacier.name
                        }
                      </strong>

                      <br />

                      RGI ID:{" "}
                      {
                        selectedGlacier.id
                      }

                      <br />
                      <br />

                      <button
                        className="popup-button"

                        onClick={() =>
                          scrollTo(
                            "analysis",
                          )
                        }
                      >

                        Analyse Glacier

                      </button>

                    </Popup>

                  </CircleMarker>

                )}

            </MapContainer>

          </div>

        </section>


        {/* =================================================
            SATELLITE
        ================================================= */}

        <section
          className="section satellite-section"
          id="satellite"
        >

          <div className="section-heading">

            <div>

              <div className="eyebrow">
                REMOTE SENSING
              </div>

              <h2>
                Satellite Monitoring
              </h2>

              <p>

                Live analysis uses the
                selected glacier to request
                the latest suitable Sentinel-2
                observation and process it
                with U-Net V3. Historical
                observations are shown only
                when the backend has processed
                data for that glacier.

              </p>

            </div>

          </div>


          <div className="satellite-grid">
          </div>


          <div className="timeline-card">

            <div className="timeline-header">

              <div>

                <strong>

                  {selectedGlacier
                    ? `${selectedGlacier.name} observations`
                    : "Observation coverage"}

                </strong>


                <span>

                  {selectedGlacier &&
                  historical.length
                    ? `${historical.length} processed historical observations`
                    : "Only processed observations are shown here."}

                </span>

              </div>


              <Satellite
                size={19}
              />

            </div>


            {historical.length >
            0 ? (

              <div className="timeline">

                <div className="timeline-line" />


                {historical.map(
                  (p) => (

                    <div
                      className="timeline-item"
                      key={
                        p.year
                      }
                    >

                      <div className="timeline-dot" />

                      <strong>
                        {p.year}
                      </strong>

                      <span>
                        {p.date}
                      </span>

                    </div>

                  ),
                )}

              </div>

            ) : (

              <div className="empty-inline">

                {selectedGlacier
                  ? "No historical observations have been processed for this glacier yet."
                  : "Select a glacier to view processed observation dates."}

              </div>

            )}

          </div>

        </section>


        {/* =================================================
            AI ANALYSIS
        ================================================= */}

        <section
          className="section"
          id="analysis"
        >

          <div className="section-heading">

            <div>

              <div className="eyebrow">
                ARTIFICIAL INTELLIGENCE
              </div>

              <h2>
                AI-Powered Glacier Analysis
              </h2>

              <p>

                Run the U-Net V3 model
                against the latest suitable
                Sentinel-2 observation for the
                selected glacier. The workflow
                is automatic — you do not need
                to upload an image.

              </p>

            </div>

          </div>


          <div className="analysis-upload-card">

            <div className="analysis-upload-header">

              <div>

                <div className="eyebrow">
                  LIVE AI ANALYSIS
                </div>


                <h2>

                  {selectedGlacier
                    ? `Analyse ${selectedGlacier.name}`
                    : "Select a glacier to analyse"}

                </h2>


                <p>

                  Fetch imagery and run
                  segmentation. No upload is
                  required.

                </p>

              </div>


              <div className="analysis-model-badge">

                <Snowflake
                  size={16}
                />

                U-Net V3

              </div>

            </div>


            <div className="analysis-upload-body">

              <div className="live-analysis-selection">

                <div>

                  <span>
                    SELECTED GLACIER
                  </span>


                  <strong>

                    {selectedGlacier?.name ??
                      "No glacier selected"}

                  </strong>


                  <small>

                    {selectedGlacier
                      ? `${selectedGlacier.latitude.toFixed(
                          4,
                        )}, ${selectedGlacier.longitude.toFixed(
                          4,
                        )}`
                      : "Choose one from the search or map."}

                  </small>

                </div>


                <button
                  className="primary-button"

                  disabled={
                    !selectedGlacier ||
                    isAnalyzing
                  }

                  onClick={
                    analyzeGlacier
                  }
                >

                  {isAnalyzing
                    ? "Analysing..."
                    : "Analyse Glacier"}


                  {!isAnalyzing && (

                    <ArrowRight
                      size={15}
                    />

                  )}

                </button>

              </div>

            </div>


            {isAnalyzing && (

              <div className="analysis-loading">

                <span className="status-dot" />

                Fetching the latest
                Sentinel-2 imagery and
                running U-Net V3. This can
                take a little while…

              </div>

            )}


            {analysisError && (

              <div className="analysis-error">

                {analysisError}

              </div>

            )}


            {liveAnalysis && (

              <div className="analysis-result">

                <div className="result-success">

                  <CheckCircle2
                    size={16}
                  />

                  Analysis completed
                  successfully

                </div>


                {liveAnalysis.classification && (

                  <div
                    style={{
                      marginTop: "24px",
                      padding: "24px",
                      border: "1px solid rgba(0, 128, 128, 0.15)",
                      borderRadius: "16px",
                      background: "#f8fcfc",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: "16px",
                        flexWrap: "wrap",
                      }}
                    >
                      <div>
                        <h3
                          style={{
                            margin: 0,
                            fontSize: "22px",
                            fontWeight: 700,
                          }}
                        >
                          Glacier Classification
                        </h3>
                        <p
                          style={{
                            margin: "6px 0 0",
                            color: "#64748b",
                          }}
                        >
                          CNN-based glacier type prediction
                        </p>
                      </div>

                      <div
                        style={{
                          padding: "8px 12px",
                          borderRadius: "999px",
                          background: "#e6f4f1",
                          color: "#0f766e",
                          fontWeight: 700,
                          fontSize: "13px",
                        }}
                      >
                        {liveAnalysis.classification.confidence_percent != null
                          ? `${liveAnalysis.classification.confidence_percent.toFixed(1)}% confidence`
                          : "CNN prediction"}
                      </div>
                    </div>

                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                        gap: "14px",
                        marginTop: "20px",
                      }}
                    >
                      <ResultStat
                        label="Predicted glacier type"
                        value={
                          liveAnalysis.classification.display_name ??
                          liveAnalysis.classification.class ??
                          "Unavailable"
                        }
                      />

                      <ResultStat
                        label="Classifier"
                        value={liveAnalysis.classification.source ?? "CNN prediction"}
                      />

                      <ResultStat
                        label="RGI verification"
                        value={
                          liveAnalysis.classification.verification?.rgi_available
                            ? "RGI inventory available"
                            : "RGI inventory unavailable"
                        }
                      />
                    </div>

                    {liveAnalysis.classification.probabilities && (
                      <div style={{ marginTop: "22px" }}>
                        <h4
                          style={{
                            margin: "0 0 14px",
                            fontSize: "17px",
                            fontWeight: 700,
                          }}
                        >
                          Class probabilities
                        </h4>

                        <div
                          style={{
                            display: "grid",
                            gap: "10px",
                          }}
                        >
                          {Object.entries(
                            liveAnalysis.classification.probabilities,
                          )
                            .sort(([, a], [, b]) => Number(b) - Number(a))
                            .map(([className, probability]) => {
                              const displayName =
                                className === "glacieret_snowfield"
                                  ? "Glacieret / Snowfield"
                                  : className === "ice_cap"
                                    ? "Ice Cap"
                                    : className === "mountain_glacier"
                                      ? "Mountain Glacier"
                                      : className;

                              const percentage = Number(probability) * 100;

                              return (
                                <div key={className}>
                                  <div
                                    style={{
                                      display: "flex",
                                      justifyContent: "space-between",
                                      gap: "12px",
                                      marginBottom: "5px",
                                      fontSize: "14px",
                                    }}
                                  >
                                    <span>{displayName}</span>
                                    <strong>{percentage.toFixed(1)}%</strong>
                                  </div>
                                  <div
                                    style={{
                                      height: "8px",
                                      borderRadius: "999px",
                                      background: "#dbe7e7",
                                      overflow: "hidden",
                                    }}
                                  >
                                    <div
                                      style={{
                                        width: `${Math.max(0, Math.min(100, percentage))}%`,
                                        height: "100%",
                                        borderRadius: "999px",
                                        background: "#0f766e",
                                      }}
                                    />
                                  </div>
                                </div>
                              );
                            })}
                        </div>
                      </div>
                    )}

                    {liveAnalysis.classification.verification && (
                      <div
                        style={{
                          marginTop: "22px",
                          padding: "16px",
                          borderRadius: "12px",
                          background: "#ffffff",
                          border: "1px solid #e2e8f0",
                        }}
                      >
                        <strong>RGI inventory metadata</strong>
                        <p
                          style={{
                            margin: "7px 0 0",
                            color: "#64748b",
                            lineHeight: 1.6,
                          }}
                        >
                          {liveAnalysis.classification.verification.note ??
                            "RGI provides inventory metadata and geometry; it is not automatically treated as ground truth for the CNN glacier-type class."}
                        </p>
                      </div>
                    )}
                  </div>

                )}


                <div className="result-grid">

                  <ResultStat
                    label="Satellite"
                    value={
                      liveAnalysis
                        .satellite
                        .source
                    }
                  />


                  <ResultStat
                    label="Model"
                    value={
                      liveAnalysis
                        .model
                        .name
                    }
                  />


                  <ResultStat
                    label="Glacier pixels"
                    value={
                      liveAnalysis.analysis.glacier_pixels.toLocaleString()
                    }
                  />


                  <ResultStat
                    label="Coverage"
                    value={`${liveAnalysis.analysis.coverage_percent.toFixed(
                      2,
                    )}%`}
                  />


                  <ResultStat
                    label="Estimated area"
                    value={`${liveAnalysis.analysis.area_km2.toFixed(
                      4,
                    )} km²`}
                  />


                  <ResultStat
                    label="RGI inventory"
                    value={
                      liveAnalysis.glacier.rgi_area_km2 !==
                      undefined
                        ? `${liveAnalysis.glacier.rgi_area_km2.toFixed(
                            4,
                          )} km²`
                        : "Unavailable"
                    }
                  />


                  <ResultStat
                    label="Resolution"
                    value={`${liveAnalysis.satellite.resolution_m} m`}
                  />


                  <ResultStat
                    label="CRS"
                    value={
                      liveAnalysis
                        .satellite
                        .crs
                    }
                  />

                </div>


                <div className="live-output-links">

                  <ResultStat
                    label="Observation date"
                    value={
                      liveAnalysis
                        .satellite
                        .observation_date
                        ? new Date(
                            liveAnalysis
                              .satellite
                              .observation_date,
                          ).toLocaleDateString()
                        : "Latest suitable observation"
                    }
                  />


                  <ResultStat
                    label="Cloud limit"
                    value={`${liveAnalysis.satellite.cloud_limit_percent}%`}
                  />


                  <ResultStat
                    label="RGI polygon"
                    value={
                      liveAnalysis.analysis
                        .rgi_polygon_applied
                        ? "Applied"
                        : "Not applied"
                    }
                  />

                </div>


                <div
                  style={{
                    display:
                      "grid",

                    gridTemplateColumns:
                      "repeat(auto-fit, minmax(260px, 1fr))",

                    gap: "18px",

                    marginTop:
                      "24px",
                  }}
                >

                  <OutputImage
                    title="AI Segmentation Overlay"
                    src={`${API}${liveAnalysis.outputs.overlay}`}
                  />


                  <OutputImage
                    title="Glacier Mask"
                    src={`${API}${liveAnalysis.outputs.mask_png}`}
                  />


                  {liveAnalysis.outputs
                    .probability_heatmap && (

                    <OutputImage
                      title="Probability Heatmap"
                      src={`${API}${liveAnalysis.outputs.probability_heatmap}`}
                    />

                  )}
                  {liveAnalysis.analysis?.xai && (
  <div
    style={{
      gridColumn: "1 / -1",
      marginTop: "24px",
      padding: "24px",
      border: "1px solid rgba(0, 128, 128, 0.15)",
      borderRadius: "16px",
      background: "#f8fcfc",
    }}
  >
    <h3
      style={{
        margin: "0 0 8px",
        fontSize: "22px",
        fontWeight: 700,
      }}
    >
      Explainable AI
    </h3>

    <p
      style={{
        margin: "0 0 20px",
        color: "#64748b",
        lineHeight: 1.6,
      }}
    >
      Pixel-level confidence produced by the U-Net V3 segmentation model.
      Higher probability indicates stronger model confidence that a pixel
      belongs to the glacier.
    </p>

    <div
      style={{
        display: "grid",
        gridTemplateColumns:
          "repeat(auto-fit, minmax(180px, 1fr))",
        gap: "14px",
      }}
    >
      <ResultStat
        label="Mean Probability"
        value={liveAnalysis.analysis.xai.mean_probability.toFixed(4)}
      />

      <ResultStat
        label="Minimum Probability"
        value={liveAnalysis.analysis.xai.minimum_probability.toFixed(4)}
      />

      <ResultStat
        label="Maximum Probability"
        value={liveAnalysis.analysis.xai.maximum_probability.toFixed(4)}
      />

      <ResultStat
        label="Segmentation Threshold"
        value={liveAnalysis.analysis.xai.threshold.toFixed(2)}
      />
    </div>

    <h4
      style={{
        margin: "24px 0 14px",
        fontSize: "17px",
        fontWeight: 700,
      }}
    >
      Confidence Distribution
    </h4>

    <div
      style={{
        display: "grid",
        gridTemplateColumns:
          "repeat(auto-fit, minmax(150px, 1fr))",
        gap: "12px",
      }}
    >
      <ResultStat
        label="Low"
        value={`${liveAnalysis.analysis.xai.confidence_distribution_percent.low.toFixed(2)}%`}
      />

      <ResultStat
        label="Uncertain"
        value={`${liveAnalysis.analysis.xai.confidence_distribution_percent.uncertain.toFixed(2)}%`}
      />

      <ResultStat
        label="Moderate"
        value={`${liveAnalysis.analysis.xai.confidence_distribution_percent.moderate.toFixed(2)}%`}
      />

      <ResultStat
        label="High"
        value={`${liveAnalysis.analysis.xai.confidence_distribution_percent.high.toFixed(2)}%`}
      />
    </div>

    <div
      style={{
        marginTop: "20px",
        padding: "14px 16px",
        borderRadius: "10px",
        background: "#eef8f8",
        color: "#475569",
        fontSize: "14px",
        lineHeight: 1.6,
      }}
    >
      {liveAnalysis.analysis.xai.explanation}
    </div>
  </div>
)}
                </div>

              </div>

            )}

          </div>

        </section>


        {/* =================================================
            HISTORY
        ================================================= */}

        <section
          className="section"
          id="history"
        >

          <div className="section-heading">

            <div>

              <div className="eyebrow">
                DATA-DRIVEN CHANGE ANALYSIS
              </div>


              <h2>

                {selectedGlacier
                  ? `${selectedGlacier.name} — Area History`
                  : "Glacier Area History"}

              </h2>


              <p>

                {selectedGlacier
                  ? "Only real processed observations for the selected glacier are displayed. No placeholder values are substituted."
                  : "Select a glacier to load its processed history."}

              </p>

            </div>


            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "12px",
              }}
            >

              {historyLoading && (

                <div className="loading-badge">
                  Loading data…
                </div>

              )}

              <button
                className="primary-button"
                type="button"
                disabled={
                  !selectedGlacier ||
                  historicalRunning ||
                  isAnalyzing
                }
                onClick={runHistoricalAnalysis}
              >

                {historicalRunning
                  ? "Running Historical Analysis…"
                  : "Refresh Historical Analysis"}

                {!historicalRunning && (
                  <ArrowRight size={15} />
                )}

              </button>

            </div>

          </div>


          {!selectedGlacier ? (

            <div className="data-empty">

              <BarChart3
                size={24}
              />

              <strong>
                Choose a glacier to begin
              </strong>

              <span>

                Search above or choose a
                glacier. The graph will update
                when processed data is available.

              </span>

            </div>

          ) : historyLoading ? (

            <div className="data-empty">

              <BarChart3
                size={24}
              />

              <strong>
                Loading historical
                analysis
              </strong>

              <span>

                Reading the selected
                glacier's processed
                observations.

              </span>

            </div>

          ) : historyError ? (

            <div className="data-empty error-state">

              <strong>
                Historical data could
                not be loaded
              </strong>

              <span>
                {historyError}
              </span>

            </div>

          ) : historical.length ===
            0 && !glimsReference ? (

            <div className="data-empty">

              <BarChart3
                size={24}
              />

              <strong>
                No historical data for{" "}
                {selectedGlacier.name}
              </strong>

              <span>

                This glacier has not been
                processed through the
                historical U-Net pipeline
                yet.

              </span>

            </div>

          ) : (

            <HistoryDashboard
              historical={
                historical
              }

              prediction={
                prediction
              }

              analysis={
                historicalAnalysis
              }

              changeAnalysis={
                changeAnalysis
              }

              glimsReference={
                glimsReference
              }

              glacierName={
                selectedGlacier.name
              }
            />

          )}

        </section>


        {/* =================================================
            REPORTS
        ================================================= */}

        <section
          className="section"
          id="reports"
        >

          <div className="section-heading">

            <div>

              <div className="eyebrow">
                DOCUMENTATION
              </div>

              <h2>
                Monitoring Reports
              </h2>

              <p>

                Export the information
                currently available for the
                selected glacier as a
                self-contained HTML report.

              </p>

            </div>

          </div>


          <div className="report-card">

            <div className="report-icon">

              <FileText
                size={23}
              />

            </div>


            <div>

              <div className="eyebrow">
                GLACIER REPORT
              </div>

              <h2>

                {selectedGlacier?.name ??
                  "No glacier selected"}

              </h2>

              <p>

                {selectedGlacier
                  ? "The report uses the selected glacier, live analysis if available, and only processed historical/prediction data."
                  : "Select a glacier first."}

              </p>

            </div>


            <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>

              <button
                className="outline-button"
                disabled={!selectedGlacier}
                onClick={viewReport}
              >
                <FileText size={15} />
                View Report
              </button>

              <button
                className="outline-button"
                disabled={!selectedGlacier || reportLoading}
                onClick={generateReport}
              >
                <Download size={15} />
                {reportLoading ? "Generating..." : "Download Report"}
              </button>

            </div>

          </div>

        </section>

      </main>


      {/* =================================================
          FOOTER
      ================================================= */}

      <footer>

        <div className="footer-brand">

          <Snowflake
            size={14}
          />

          GlacierAI

        </div>


        <span>

          AI-Based Glacier Monitoring &
          Retreat Analysis

        </span>


        <button
          type="button"
          aria-label="Back to top"
          title="Back to top"

          onClick={() =>
            window.scrollTo({
              top: 0,
              behavior:
                "smooth",
            })
          }
        >

          ↑

        </button>

      </footer>

    </div>

  );
}


/* =========================================================
   HISTORY DASHBOARD
========================================================= */

function HistoryDashboard({
  historical,
  prediction,
  analysis,
  changeAnalysis,
  glimsReference,
  glacierName,
}: {
  historical: HistoricalPoint[];
  prediction: PredictionPoint[];
  analysis: HistoricalAnalysisData | null;
  changeAnalysis: ChangeAnalysisData | null;
  glimsReference: GlimsReference | null;
  glacierName: string;
}) {

  const allValues = [

    ...historical.map(
      (p) =>
        p.area_km2,
    ),

    ...prediction.map(
      (p) =>
        Number(
          p.predicted_area_km2,
        ),
    ),

  ].filter(
    Number.isFinite,
  );


  const min =
    Math.min(
      ...allValues,
    );


  const max =
    Math.max(
      ...allValues,
    );


  const range =
    Math.max(
      max - min,
      1,
    );


  const width = 900;

  const height = 330;

  const left = 64;

  const right = 28;

  const top = 34;

  const bottom = 54;


  const plotWidth =
    width -
    left -
    right;


  const plotHeight =
    height -
    top -
    bottom;


  const points = [

    ...historical,

    ...prediction.map(
      (p) => ({
        year:
          p.year,

        date:
          "",

        area_km2:
          Number(
            p.predicted_area_km2,
          ),

      }),
    ),

  ];


  const x = (
    index: number,
  ) =>
    left +
    (index *
      plotWidth) /
      Math.max(
        points.length -
          1,
        1,
      );


  const y = (
    value: number,
  ) =>
    top +
    ((max - value) /
      range) *
      plotHeight;


  const historicalPath =
    historical
      .map(
        (
          p,
          i,
        ) =>
          `${x(i)},${y(
            p.area_km2,
          )}`,
      )
      .join(" ");


  const predictionStart =
    historical.length -
    1;


  const predictionPath =
    prediction.length &&
    historical.length
      ? [

          `${x(
            predictionStart,
          )},${y(
            historical[
              historical.length -
                1
            ].area_km2,
          )}`,

          ...prediction.map(
            (
              p,
              i,
            ) =>
              `${x(
                historical.length +
                  i,
              )},${y(
                Number(
                  p.predicted_area_km2,
                ),
              )}`,
          ),

        ].join(" ")

      : "";


  const first =
    historical[0]
      ?.area_km2;


  const last =
    historical[
      historical.length -
        1
    ]?.area_km2;


  const change =
    first !== undefined &&
    last !== undefined
      ? last - first
      : 0;

  return (

    <div className="history-dashboard">


      {(historical.length > 0 || prediction.length > 0) && (
      <div className="history-chart-card">

        <div className="chart-header">

          <div>

            <strong>
              Historical Glacier Area
            </strong>

            <span>

              U-Net V3 historical estimates
              for{" "}
              {glacierName}

            </span>

          </div>


          <BarChart3
            size={18}
          />

        </div>


        <div className="chart-wrap">

          <svg
            viewBox={`0 0 ${width} ${height}`}
            className="area-chart"
            role="img"
            aria-label={`Historical glacier area for ${glacierName}`}
          >

            {[0, 0.25, 0.5, 0.75, 1].map(
              (ratio) => {

                const value =
                  max -
                  ratio *
                    range;


                const yy =
                  top +
                  ratio *
                    plotHeight;


                return (

                  <g
                    key={
                      ratio
                    }
                  >

                    <line
                      x1={
                        left
                      }

                      x2={
                        width -
                        right
                      }

                      y1={
                        yy
                      }

                      y2={
                        yy
                      }

                      className="grid-line"
                    />


                    <text
                      x={
                        left -
                        10
                      }

                      y={
                        yy +
                        4
                      }

                      textAnchor="end"

                      className="axis-label"
                    >

                      {value.toFixed(
                        1,
                      )}

                    </text>

                  </g>

                );

              },
            )}


            {historicalPath && (

              <polyline
                points={
                  historicalPath
                }

                className="history-line"
              />

            )}


            {predictionPath && (

              <polyline
                points={
                  predictionPath
                }

                className="prediction-line"
              />

            )}


            {points.map(
              (
                p,
                i,
              ) => (

                <g
                  key={`${p.year}-${i}`}
                >

                  <circle
                    cx={x(i)}
                    cy={y(
                      p.area_km2,
                    )}
                    r="5"

                    className={
                      i <
                      historical.length
                        ? "history-point"
                        : "prediction-point"
                    }
                  />


                  <text
                    x={x(i)}

                    y={
                      height -
                      25
                    }

                    textAnchor="middle"

                    className="axis-label"
                  >

                    {p.year}

                  </text>

                </g>

              ),
            )}

          </svg>

        </div>


        <div className="chart-legend">

          <span>

            <i className="legend-history" />

            Historical U-Net V3

          </span>


          {prediction.length >
            0 && (

            <span>

              <i className="legend-prediction" />

              Future trend estimate

            </span>

          )}

        </div>

      </div>
      )}


      {glimsReference?.success &&
        (glimsReference.historical_records?.length ?? 0) > 0 && (
        <div className="history-table-card">
          <div className="chart-header">
            <div>
              <strong>GLIMS Historical Reference</strong>
              <span>
                Independent historical glacier-outline records associated
                with this RGI glacier
              </span>
            </div>
            <Database size={18} />
          </div>

          <div className="metric-row">
            <MetricCard
              label="GLIMS ID"
              value={glimsReference.glims_id ?? "—"}
            />
            <MetricCard
              label="Reference records"
              value={`${glimsReference.historical_records?.length ?? 0}`}
            />
            <MetricCard
              label="GLIMS layer"
              value={glimsReference.glims_layer ?? "GLIMS"}
            />
          </div>

          <div className="history-table">
            <div className="history-row">
              <strong>Year</strong>
              <strong>Observation date</strong>
              <strong>GLIMS area</strong>
              <strong>Source</strong>
            </div>

            {glimsReference.historical_records?.map((record, index) => (
              <div
                className="history-row"
                key={`${record.glims_id ?? "glims"}-${record.date ?? index}`}
              >
                <span>{record.year ?? "—"}</span>
                <span>
                  {record.date
                    ? new Date(record.date).toLocaleDateString()
                    : "—"}
                </span>
                <span>
                  {record.area_km2 != null
                    ? `${Number(record.area_km2).toFixed(4)} km²`
                    : "—"}
                </span>
                <span>{record.source ?? "—"}</span>
              </div>
            ))}
          </div>

          <p className="history-note">
            GLIMS records are shown as an independent historical reference.
            They are not merged with the U-Net observations because the
            observations can come from different dates, sources and
            delineation methods.
          </p>
        </div>
      )}

      {(analysis?.overall_observed_change ||
        (changeAnalysis?.spatial_boundary_change &&
          changeAnalysis.spatial_boundary_change.length > 0)) && (

        <div className="history-table-card">

          <div className="chart-header">

            <div>

              <strong>
                Area &amp; Spatial Change Summary
              </strong>

              <span>
                Historical U-Net V3 estimates and year-to-year mask changes
              </span>

            </div>

          </div>


          {analysis?.overall_observed_change && (

            <div className="metric-row">

              <MetricCard
                label={`${analysis.overall_observed_change.start_year} Area`}
                value={`${analysis.overall_observed_change.start_area_km2.toFixed(
                  4,
                )} km²`}
              />

              <MetricCard
                label={`${analysis.overall_observed_change.end_year} Area`}
                value={`${analysis.overall_observed_change.end_area_km2.toFixed(
                  4,
                )} km²`}
              />

              <MetricCard
                label="Observed area change"
                value={`${analysis.overall_observed_change.total_change_km2 >= 0
                  ? "+"
                  : ""}${analysis.overall_observed_change.total_change_km2.toFixed(
                  4,
                )} km²`}
              />

              <MetricCard
                label="Area change rate"
                value={
                  analysis.overall_observed_change
                    .annualized_change_km2_per_year !== null
                    ? `${analysis.overall_observed_change
                        .annualized_change_km2_per_year >= 0
                        ? "+"
                        : ""}${analysis.overall_observed_change
                        .annualized_change_km2_per_year.toFixed(
                        4,
                      )} km²/year`
                    : "—"
                }
              />

            </div>

          )}


          <p className="history-note">

            Historical areas are U-Net V3 model estimates. Independent
            historical glacier boundaries are not available in the current
            pipeline, so these observations are not independently validated.
            Terminus retreat rate in m/year is not reported.

          </p>


          {changeAnalysis?.spatial_boundary_change &&
            changeAnalysis.spatial_boundary_change.length > 0 && (

              <>

                <div
                  className="chart-header"
                  style={{ marginTop: "18px" }}
                >

                  <div>

                    <strong>
                      Spatial Mask Change
                    </strong>

                    <span>
                      Pixel-mask differences between consecutive historical observations
                    </span>

                  </div>

                </div>


                <div className="history-table">

                  <div className="history-row">

                    <strong>Period</strong>
                    <strong>Lost area</strong>
                    <strong>Gained area</strong>
                    <strong>Mask IoU</strong>

                  </div>


                  {changeAnalysis.spatial_boundary_change.map((change) => (

                    <div
                      className="history-row"
                      key={`spatial-${change.from_year}-${change.to_year}`}
                    >

                      <span>
                        {change.from_year} → {change.to_year}
                      </span>

                      <span>
                        {change.lost_area_km2?.toFixed(4) ?? "—"} km²
                      </span>

                      <span>
                        {change.gained_area_km2?.toFixed(4) ?? "—"} km²
                      </span>

                      <strong>
                        {change.spatial_iou != null
                          ? change.spatial_iou.toFixed(4)
                          : "—"}
                      </strong>

                    </div>

                  ))}

                </div>


                <p className="history-note">

                  Mask IoU describes spatial overlap between consecutive
                  U-Net V3 masks. It is not independent model validation
                  and should not be interpreted as a physical retreat rate.

                </p>

              </>

            )}

        </div>

      )}


      {historical.length > 0 && (
      <>
      <div className="metric-row">

        <MetricCard
          label={`${historical[0].year} Area`}
          value={`${first?.toFixed(
            4,
          )} km²`}
        />


        <MetricCard
          label={`${historical[historical.length - 1].year} Area`}
          value={`${last?.toFixed(
            4,
          )} km²`}
        />


        <MetricCard
          label="Observed change"
          value={`${
            change >=
            0
              ? "+"
              : ""
          }${change.toFixed(
            4,
          )} km²`}
        />


        {prediction.length >
          0 && (

          <MetricCard
            label={`${prediction[0].year}–${prediction[prediction.length - 1].year} trend`}
            value={`${(
              Number(
                prediction[
                  prediction.length -
                    1
                ]
                  .predicted_area_km2,
              ) -
              Number(
                prediction[0]
                  .predicted_area_km2,
              )
            ).toFixed(
              4,
            )} km²`}
          />

        )}

      </div>


      <div className="metric-row">

        <MetricCard
          label="Processed observations"
          value={`${historical.length}`}
        />

        <MetricCard
          label="Validation status"
          value="Not independently validated"
        />

      </div>


      <div className="history-table-card">

        <div className="chart-header">

          <div>

            <strong>
              Historical observations
            </strong>

            <span>
              Processed dates and
              model-estimated area
            </span>

          </div>

        </div>


        <div className="history-table">

          <div className="history-row">

            <strong>Year</strong>
            <strong>Observation date</strong>
            <strong>U-Net V3 estimated area</strong>
            <strong>Validation</strong>

          </div>


          {historical.map(
            (p) => (

              <div
                className="history-row"
                key={p.year}
              >

                <span>
                  {p.year}
                </span>

                <span>
                  {p.date
                    ? new Date(p.date).toLocaleDateString()
                    : "—"}
                </span>

                <span>
                  {p.area_km2.toFixed(4)} km²
                </span>

                <strong>
                  Not independently validated
                </strong>

              </div>

            ),
          )}

        </div>

      </div>
      </>

      )}

      {prediction.length >
        0 && (

        <div className="history-table-card">

          <div className="chart-header">

            <div>

              <strong>
                Future area estimates
              </strong>

              <span>

                Trend-based estimates
                from the available
                historical observations

              </span>

            </div>

          </div>


          <div className="history-table">

            <div className="history-row">

              <strong>Year</strong>
              <strong>Predicted area</strong>
              <strong>Estimate type</strong>

            </div>


            {prediction.map(
              (p) => (

                <div
                  className="history-row"
                  key={p.year}
                >

                  <span>
                    {p.year}
                  </span>

                  <span>
                    {Number(p.predicted_area_km2).toFixed(4)} km²
                  </span>

                  <strong>
                    Trend estimate
                  </strong>

                </div>

              ),
            )}

          </div>


          <p className="history-note">

            These are trend-based estimates from the available
            historical U-Net V3 area estimates, not definitive
            physical climate predictions.

          </p>

        </div>

      )}

    </div>

  );
}


/* =========================================================
   OUTPUT IMAGE
========================================================= */

function OutputImage({
  title,
  src,
}: {
  title: string;
  src: string;
}) {

  return (

    <div
      style={{
        border:
          "1px solid var(--border-color, #d8e4ef)",

        borderRadius:
          "14px",

        overflow:
          "hidden",

        background:
          "var(--card-bg, #ffffff)",
      }}
    >

      <div
        style={{
          padding:
            "12px 14px",

          fontWeight:
            600,
        }}
      >

        {title}

      </div>


      <a
        href={src}
        target="_blank"
        rel="noreferrer"
      >

        <img
          src={src}
          alt={title}

          style={{
            display:
              "block",

            width:
              "100%",

            height:
              "220px",

            objectFit:
              "contain",

            background:
              "#eef4f8",
          }}
        />

      </a>

    </div>

  );
}


/* =========================================================
   SMALL COMPONENTS
========================================================= */

function MetricCard({
  label,
  value,
}: {
  label: string;
  value: string;
}) {

  return (

    <div className="metric-card">

      <span>
        {label}
      </span>

      <strong>
        {value}
      </strong>

    </div>

  );
}


function ResultStat({
  label,
  value,
}: {
  label: string;
  value: string;
}) {

  return (

    <div className="result-stat">

      <span>
        {label}
      </span>

      <strong>
        {value}
      </strong>

    </div>

  );
}


export default App;