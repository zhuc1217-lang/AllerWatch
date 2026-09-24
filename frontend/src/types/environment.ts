export type CurrentEnvironment = {
  timestamp: string
  weather_timestamp: string | null
  air_quality_timestamp: string | null
  status: 'available' | 'partial'
  temperature_c: number | null
  relative_humidity: number | null
  pm2_5: number | null
  pm10: number | null
  us_aqi: number | null
  latitude: number
  longitude: number
}
