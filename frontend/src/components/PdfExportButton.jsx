import React, { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import jsPDF from "jspdf";
import html2canvas from "html2canvas";
import { toast } from "sonner";
import { DISCLAIMER_TEXT } from "./Disclaimer";

export default function PdfExportButton({ targetId = "dashboard-main", filename }) {
  const [loading, setLoading] = useState(false);

  const exportPdf = async () => {
    const el = document.getElementById(targetId);
    if (!el) {
      toast.error("Nothing to export yet");
      return;
    }
    setLoading(true);
    // Temporarily prepend a visible disclaimer banner inside the target so it lands on page 1
    const disclaimer = document.createElement("div");
    disclaimer.id = "__pdf_disclaimer__";
    disclaimer.style.cssText =
      "padding:14px 18px;margin-bottom:12px;border:1px solid #b45309;background:#451a03;color:#fde68a;font-size:11px;line-height:1.5;letter-spacing:0.04em;";
    disclaimer.textContent = "DISCLAIMER · " + DISCLAIMER_TEXT;
    el.prepend(disclaimer);
    try {
      const canvas = await html2canvas(el, {
        backgroundColor: "#09090b",
        scale: 1.4,
        useCORS: true,
        logging: false,
        windowWidth: el.scrollWidth,
        windowHeight: el.scrollHeight,
      });
      const imgData = canvas.toDataURL("image/jpeg", 0.85);
      const pdf = new jsPDF({ orientation: "portrait", unit: "pt", format: "a4" });
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const imgWidth = pageWidth;
      const imgHeight = (canvas.height * imgWidth) / canvas.width;
      let heightLeft = imgHeight;
      let position = 0;
      pdf.addImage(imgData, "JPEG", 0, position, imgWidth, imgHeight);
      heightLeft -= pageHeight;
      while (heightLeft > 0) {
        position = heightLeft - imgHeight;
        pdf.addPage();
        pdf.addImage(imgData, "JPEG", 0, position, imgWidth, imgHeight);
        heightLeft -= pageHeight;
      }
      pdf.save(filename || `stock-sentinel-${Date.now()}.pdf`);
      toast.success("PDF exported");
    } catch (e) {
      toast.error("PDF export failed: " + (e.message || ""));
    } finally {
      const node = document.getElementById("__pdf_disclaimer__");
      if (node) node.remove();
      setLoading(false);
    }
  };

  return (
    <button
      onClick={exportPdf}
      disabled={loading}
      data-testid="export-pdf-btn"
      className="flex items-center gap-1.5 px-2.5 py-1 text-[10px] tracking-widest uppercase font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-100 border border-zinc-700 disabled:opacity-50 transition-colors"
    >
      {loading ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
      {loading ? "Generating…" : "Export PDF"}
    </button>
  );
}
