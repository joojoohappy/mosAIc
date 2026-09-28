import { Shell, Icon } from "@/components/ui";
const principles = [
  {
    icon: "0ab76",
    title: "Creator Attribution Always",
    description:
      "Original creators and sources are never erased. Every derivative prompt or output links back to its ancestor, keeping the creative tree unbroken.",
  },
  {
    icon: "ebea2",
    title: "Accessible Creativity",
    description:
      "Anyone can explore, learn from, and participate in creative AI. We demystify the configurations so you can focus strictly on the art.",
  },
  {
    icon: "8049c",
    title: "Transparent Process",
    description:
      "Recipe context, result sources, and creator attribution are visible by design. Private prompts remain on the server.",
  },
  {
    icon: "65209",
    title: "Community-Driven",
    description:
      "Built by and for the creative community. Leveling the playing field so independent artists can collaborate and claim ownership of their pipelines.",
  },
];
export default function About() {
  return (
    <Shell about>
      <main>
        <section className="about-hero">
          <h1>About mosAIc</h1>
          <p>A place to explore, understand, and participate in Creative AI.</p>
        </section>
        <section className="mission">
          <div>
            <span className="eyebrow">The Mission</span>
            <h2>Preserving creative lineage</h2>
            <p>
              Our platform allows anyone to discover creative AI recipes shared
              by others, make their own unique versions, and experiment
              freely—all while preserving original creator attribution and
              tracing the evolutionary lineage of every prompt and model
              configuration.
            </p>
          </div>
          <div className="lineage">
            <span>Original Recipe</span>
            <Icon name="ec6b1" size={24} height={2} />
            <div>
              <span className="remix">Your Remix A</span>
              <span>Remix B</span>
            </div>
          </div>
        </section>
        <section className="principles">
          <span className="eyebrow">Core Values</span>
          <h2>Our Principles</h2>
          <div className="principles-grid">
            {principles.map((p) => (
              <article key={p.title}>
                <h3>
                  <span className="principle-icon">
                    <Icon name={p.icon} size={18} />
                  </span>
                  {p.title}
                </h3>
                <p>{p.description}</p>
              </article>
            ))}
          </div>
        </section>
        <section className="roadmap">
          <span className="eyebrow">Roadmap</span>
          <h2>What&apos;s Next</h2>
          <div className="roadmap-grid">
            {[
              {
                title: "Recipe Collections",
                text: "Group and organize related workflows into curated aesthetic boards.",
              },
              {
                title: "Creator Profiles",
                text: "Showcase your generated lineage trees and published prompt pipelines.",
              },
              {
                title: "Developer API",
                text: "Programmatically execute, remix, and query lineage datasets.",
              },
              {
                title: "Challenges",
                text: "Participate in community-voted design and prompt-engineering sprints.",
              },
            ].map((item) => (
              <article key={item.title}>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </article>
            ))}
          </div>
        </section>
      </main>
    </Shell>
  );
}
