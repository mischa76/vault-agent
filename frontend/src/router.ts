// A path router over history.pushState; the backend answers any client route with index.html.
import { useEffect, useState } from "react";

export type Perspective = "project" | "run" | "review" | "model" | "artefacts" | "log";
export const PERSPECTIVES: Perspective[] = ["project", "run", "review", "model", "artefacts", "log"];

export interface Route {
  project: string | null;
  run: string | null;
  perspective: Perspective;
}

export function parseRoute(pathname: string): Route {
  const parts = pathname.split("/").filter(Boolean).map(decodeURIComponent);
  const route: Route = { project: null, run: null, perspective: "project" };
  for (let i = 0; i < parts.length; i += 2) {
    const key = parts[i], value = parts[i + 1];
    if (key === "p" && value) route.project = value;
    else if (key === "r" && value) route.run = value;
    else if (key === "v" && value && (PERSPECTIVES as string[]).includes(value)) route.perspective = value as Perspective;
  }
  if (route.run && route.perspective === "project") route.perspective = "run";
  return route;
}

export function routePath(route: Partial<Route>): string {
  const parts: string[] = [];
  if (route.project) parts.push("p", encodeURIComponent(route.project));
  if (route.run) parts.push("r", encodeURIComponent(route.run));
  if (route.perspective) parts.push("v", route.perspective);
  return "/" + parts.join("/");
}

export function useRoute(): [Route, (next: Partial<Route>) => void] {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.pathname));
  useEffect(() => {
    const onPop = () => setRoute(parseRoute(window.location.pathname));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  const navigate = (next: Partial<Route>) => {
    const merged: Route = { ...route, ...next };
    if (next.project !== undefined && next.run === undefined) merged.run = null;
    const path = routePath(merged);
    if (path !== window.location.pathname) window.history.pushState(null, "", path);
    setRoute(parseRoute(path));
  };
  return [route, navigate];
}
