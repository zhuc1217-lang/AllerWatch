export type CurrentEnvironment = {
  timestamp: string
  weather_timestamp: string | null
  air_quality_timestamp: string | null
  status: 'available' | 'partial'
  temperature_c: number | null
  relative_humidity: number | null
  pm2_5: number | null
  pm10: number | null
  nitrogen_dioxide: number | null
  sulfur_dioxide: number | null
  carbon_monoxide: number | null
  ozone: number | null
  china_aqi_estimate: number | null
  china_aqi_primary_pollutant: string | null
  latitude: number
  longitude: number
}
