import { describe, expect, it } from "vitest";
import { parseRoute, routePath } from "./router";

describe("router", () => {
  it("round-trips project, run and perspective", () => {
    const path = routePath({ project: "bank-demo", run: "bank-demo:20261011T100000000000Z", perspective: "review" });
    expect(path).toBe("/p/bank-demo/r/bank-demo%3A20261011T100000000000Z/v/review");
    expect(parseRoute(path)).toEqual({ project: "bank-demo", run: "bank-demo:20261011T100000000000Z", perspective: "review" });
  });
  it("defaults to the project perspective without a run and to run with one", () => {
    expect(parseRoute("/").perspective).toBe("project");
    expect(parseRoute("/p/x/r/x:1").perspective).toBe("run");
    expect(parseRoute("/p/x/v/nonsense").perspective).toBe("project");
  });
});
