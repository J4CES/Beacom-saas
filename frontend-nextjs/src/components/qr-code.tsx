"use client";

import QRCode from "qrcode";
import { useEffect, useState } from "react";

/** QR code du lien public, généré dans le navigateur (aucun service tiers ne voit le lien). */
export function QrCode({ texte, nom }: { texte: string; nom: string }) {
  const [image, setImage] = useState<string | null>(null);
  useEffect(() => {
    QRCode.toDataURL(texte, { width: 480, margin: 2, errorCorrectionLevel: "M" }).then(setImage).catch(() => setImage(null));
  }, [texte]);
  if (!image) return <div className="h-40 w-40 animate-pulse rounded-lg bg-grille" />;
  return (
    <div className="flex flex-col items-center gap-2">
      {/* eslint-disable-next-line @next/next/no-img-element -- image générée localement (data URL) */}
      <img src={image} alt={`QR code pour laisser un avis sur ${nom}`} className="h-40 w-40 rounded-lg bg-white p-1" />
      <a className="bouton-discret text-xs" href={image} download={`qr-avis-${nom.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.png`}>
        Télécharger pour impression
      </a>
    </div>
  );
}
