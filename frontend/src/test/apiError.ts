import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";

/** An error shaped like the API's refusals: a status and a `detail` sentence. */
export function apiError(status: number, detail: string): AxiosError {
  const config = { headers: {} } as InternalAxiosRequestConfig;
  const response = { status, data: { detail }, statusText: "", headers: {}, config } as AxiosResponse;
  return new AxiosError(detail, String(status), config, undefined, response);
}
