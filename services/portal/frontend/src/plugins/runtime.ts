export type RuntimeConfig = {
  PORTAL_BACKEND_HOST_IP: string,
  BACKEND_PORT: string|number,
  SSL: boolean
};

let _config: RuntimeConfig | null = null;

// Load the config asynchronously (from /runtime-config.json)
export async function loadRuntimeConfig(): Promise<RuntimeConfig> {
  if (_config) return _config; // already loaded

  const res = await fetch('/runtime-config.json', { cache: 'no-cache' });

  if (!res.ok) throw new Error('Failed to load runtime config');

  _config = (await res.json()) as RuntimeConfig; // assert type
  return _config;
}

// Get the config synchronously after loading
export function getRuntimeConfig(): RuntimeConfig {
  if (!_config) {
    throw new Error('Runtime config not loaded yet');
  }
  return _config;
}
