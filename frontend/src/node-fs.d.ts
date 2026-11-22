// The one Node call a test makes (Buttons.test.tsx reads the palette's tokens from styles.css);
// declared here so the app's type roots stay the browser's.
declare module "node:fs" {
  export function readFileSync(path: string, encoding: "utf8"): string;
}
