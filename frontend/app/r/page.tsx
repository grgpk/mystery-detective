import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { fromSearchParams, headline, toSearchParams } from "@/lib/share";

type Props = PageProps<"/r">;

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const result = fromSearchParams(await searchParams);
  if (!result) return { title: "The Last Alibi" };
  const title = `${result.title}: ${headline(result)}`;
  const image = `/api/share-card?${toSearchParams(result)}`;
  return {
    title,
    description: "A new golden-age murder mystery every time you press Play, and the suspects talk back.",
    openGraph: { title, images: [{ url: image, width: 1200, height: 630 }] },
    twitter: { card: "summary_large_image", title, images: [image] },
  };
}

export default function SharedResultPage({ searchParams }: Props) {
  return (
    <main className="grid min-h-dvh place-items-center px-4 py-10">
      <article className="paper animate-deal w-full max-w-xl rounded-sm p-7 text-center">
        <p className="font-type text-ink-soft text-xs tracking-[0.35em] uppercase">The Last Alibi</p>
        <Suspense fallback={<h1 className="font-type mt-3 text-3xl">Opening the file…</h1>}>
          <Result searchParams={searchParams} />
        </Suspense>
        <p className="mt-5">A new golden-age mystery every time you press Play, and the suspects talk back.</p>
        <Link
          href="/"
          className="font-type bg-ink text-paper hover:bg-ink/85 mt-6 inline-block rounded-sm px-5 py-2 tracking-wide uppercase"
        >
          Take the case
        </Link>
      </article>
    </main>
  );
}

/** The only part that depends on the link; everything around it is prerendered. */
async function Result({ searchParams }: Pick<Props, "searchParams">) {
  const result = fromSearchParams(await searchParams);
  if (!result) return <h1 className="font-type mt-3 text-3xl">A murder is waiting</h1>;
  return (
    <>
      <h1 className="font-type mt-3 text-3xl">{result.title}</h1>
      <p className="text-string font-type mt-2 text-lg">{headline(result)}</p>
      <p className="text-ink-soft mt-1">{result.score} / 100</p>
    </>
  );
}
