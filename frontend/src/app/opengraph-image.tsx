import { ImageResponse } from "next/og";
import LogoMark from "@/components/LogoMark";

export const alt = "AgriSense — Know what your Florida land is built to grow.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", width: "100%", height: "100%", padding: 80, background: "#f4ecd8", color: "#1f2a1f" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 24, color: "#2f6b3a", fontSize: 72, fontWeight: 700 }}><LogoMark size={90} />AgriSense</div>
      <div style={{ display: "flex", marginTop: 40, fontSize: 58, lineHeight: 1.15, maxWidth: 990 }}>Know what your Florida land is built to grow.</div>
    </div>, size,
  );
}
