"use client";
import Link from "next/link";
import { useState } from "react";
import { mosaicApi } from "@mosaic/api";
import { useApiData, useFavorites } from "../hooks";
import {
  filterOptions,
  DataState,
  Placeholder,
  recipeTags,
  Shell,
  Tags,
} from "../ui";

const listRecipes = (_id: string) => mosaicApi.listRecipes();

export function Discover({ savedOnly = false }: { savedOnly?: boolean }) {
  const { data, error, loading, retry } = useApiData("recipes", listRecipes);
  const [category, setCategory] = useState("All");
  const { ids, ready } = useFavorites();
  const recipes = data?.filter(
    (r) =>
      (!savedOnly || ids.includes(r.id)) &&
      (category === "All" || recipeTags(r).includes(category)),
  );
  return (
    <Shell>
      <main className="body discover">
        <section className="hero">
          <h1>
            {savedOnly
              ? "Your favorite creative AI recipes"
              : "Explore creative AI recipes from the community"}
          </h1>
          <p>
            {savedOnly
              ? "Recipes you saved on this device."
              : "Browse prompts, styles, and techniques shared by creators."}
          </p>
        </section>
        <section className="categories">
          <h2>Categories</h2>
          <div className="chips">
            {filterOptions(data || []).map((c) => (
              <button
                key={c}
                className="chip"
                aria-pressed={category === c}
                onClick={() => setCategory(c)}
              >
                {c}
              </button>
            ))}
          </div>
        </section>
        <section className="featured" id="recipes">
          <h2>{savedOnly ? "My Recipes" : "Featured Community Recipes"}</h2>
          {loading || (savedOnly && !ready) ? (
            <DataState loading />
          ) : error ? (
            <DataState error={error} retry={retry} />
          ) : (
            <div className="recipe-grid">
              {recipes?.map((r) => (
                <article className="recipe-card" key={r.id}>
                  <Link
                    className="card-link"
                    href={`/recipe/${encodeURIComponent(r.id)}`}
                    aria-label={r.title}
                  >
                    {r.previewImageUrl ? (
                      <div className="card-image">
                        <img src={r.previewImageUrl} alt={r.title} />
                      </div>
                    ) : (
                      <Placeholder
                        label="Recipe Thumbnail"
                        className="card-image"
                      />
                    )}
                    <div className="card-content">
                      <h3>{r.title}</h3>
                      <p>
                        {r.creatorName ? `by ${r.creatorName}` : "來源待確認"}
                      </p>
                      <Tags tags={recipeTags(r)} />
                    </div>
                  </Link>
                </article>
              ))}
              {recipes?.length === 0 && (
                <p className="empty">
                  {savedOnly
                    ? "這個分類尚無已收藏的 recipe。"
                    : "這個分類目前沒有 recipe。"}
                </p>
              )}
            </div>
          )}
        </section>
      </main>
    </Shell>
  );
}
