import { Link } from 'react-router-dom'

const TIMELINE = [
  { year: '1975', text: 'A small Yale memorabilia shop opens its doors on Broadway, steps from Old Campus.' },
  { year: 'Growing up', text: 'Screen printing, embroidery, and in-house graphic design join the counter.' },
  { year: 'Today', text: 'A second generation of the family keeps the shop running with the same care for every customer.' },
]

const MAKE = [
  { title: 'All 14 residential colleges', text: 'From Benjamin Franklin to Trumbull. Wear your college crest with pride.', to: '/products?collection=residential-colleges' },
  { title: 'Varsity sports', text: 'Crew, hockey, fencing, sailing, track, and the rest of the Bulldog roster.', to: '/products?collection=game-day' },
  { title: 'Grad & professional schools', text: 'Law, music, and more, for the degrees that come after the first one.', to: '/products?q=school' },
  { title: 'The whole family', text: 'Alumni and class-year gear, plus picks for Yale moms, dads, and grandparents.', to: '/products?collection=gifts' },
]

export default function About() {
  return (
    <div className="page about">
      <header className="about__hero">
        <p className="eyebrow">About Campus Customs</p>
        <h1 className="display">A New Haven family business, dressed in Bulldog blue.</h1>
        <p className="lede">
          We've been part of the Yale neighborhood for about fifty years. What began as a tiny souvenir counter is now a
          full print-and-stitch shop. We make officially licensed apparel for students, alumni, teams, and anyone who's
          ever cheered "Boola Boola."
        </p>
      </header>

      <div className="about__grid">
        <section>
          <h2 className="h2">Our story</h2>
          <p>
            Campus Customs is family-run and proudly local. Brothers Joel and Jeremy Cobden carry on what their father
            started: honest service, fair dealing, and merch that people are glad to wear for years.
          </p>
          <p>
            Our screen printing and embroidery happen close to home, so a design can go from sketch to sweatshirt fast.
            That's how we keep up with reunions, team events, and every new class that arrives each fall.
          </p>
          <ol className="timeline">
            {TIMELINE.map((t) => (
              <li key={t.year}><strong>{t.year}</strong><span>{t.text}</span></li>
            ))}
          </ol>
        </section>

        <section>
          <h2 className="h2">What we make</h2>
          <ul className="make-list">
            {MAKE.map((m) => (
              <li key={m.title}>
                <Link to={m.to}><strong>{m.title}</strong><span>{m.text}</span></Link>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <div className="info-row">
        <section id="returns">
          <h3 className="h3">Returns, simply</h3>
          <p className="muted">
            You have 30 days from shipping to return unworn items with tags attached. Refunds post 2–10 business days after
            we receive them. Custom-made pieces are final sale.
          </p>
        </section>
        <section>
          <h3 className="h3">Visit the shop</h3>
          <p className="muted">57 Broadway, New Haven, CT 06511, right across from campus.</p>
        </section>
        <section>
          <h3 className="h3">Questions about an order?</h3>
          <p className="muted">
            Email <a href="mailto:orderdept@campuscustoms.com">orderdept@campuscustoms.com</a> or call (475) 301-4205.
            You can also ask the Bulldog, our shopping assistant, from the Ask button at the top of any page.
          </p>
        </section>
      </div>
    </div>
  )
}
