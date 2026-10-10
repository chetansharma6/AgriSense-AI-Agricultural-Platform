import { ImageResponse } from "next/og";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

export const alt = "AgriSense — Know what your Florida land is built to grow.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OpenGraphImage() {
  const logo = await readFile(join(process.cwd(), "public", "logo-reference.png"));
  const logoUrl = `data:image/png;base64,${logo.toString("base64")}`;
  return new ImageResponse(
    <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", width: "100%", height: "100%", padding: 64, background: "#f4ecd8", color: "#1f2a1f" }}>
      {/* ImageResponse consumes the original transparent wordmark directly. */}
      <img src={logoUrl} alt="AgriSense" width={900} height={300} />
      <div style={{ display: "flex", marginTop: 24, fontSize: 52, lineHeight: 1.15, maxWidth: 990 }}>Know what your Florida land is built to grow.</div>
    </div>, size,
  );
}
