# -*- coding: utf-8 -*-
"""TOC table for Conway, GTM 159 "Functions of One Complex Variable II".

Transcribed page-by-page from the book's own Contents (physical pages 10-12
of the scan, printed xi-xiii) plus the running heads. Verified visually.

Front matter: printed roman r == physical page + 1   (p7 = viii, p15 = xvi)
Body:         printed arabic n == physical page - 15  (p16 = printed 1)
"""

K = 15  # physical(1-based) = printed + K

# (level, label, printed page, kind, key)
# kind: 'chap' -> "Chapter N" + title heading ; 'sec' -> section heading
#       'back' -> centred/back-matter heading ; 'front' -> fixed physical page
FRONT = [
    (1, "Title Page",                 2, 'front', 'title'),
    (1, "Preface",                    6, 'front', 'preface'),
    (1, "Contents of Volume II",     10, 'front', 'toc2'),
    (1, "Contents of Volume I",      14, 'front', 'toc1'),
]

CH = [
    (13, "Return to Basics", 1, [
        (1, "Regions and Curves", 1),
        (2, "Derivatives and Other Recollections", 6),
        (3, "Harmonic Conjugates and Primitives", 14),
        (4, "Analytic Arcs and the Reflection Principle", 16),
        (5, "Boundary Values for Bounded Analytic Functions", 21),
    ]),
    (14, "Conformal Equivalence for Simply Connected Regions", 29, [
        (1, "Elementary Properties and Examples", 29),
        (2, "Crosscuts", 33),
        (3, "Prime Ends", 40),
        (4, "Impressions of a Prime End", 45),
        (5, "Boundary Values of Riemann Maps", 48),
        (6, "The Area Theorem", 56),
        (7, "Disk Mappings: The Class S", 61),
    ]),
    (15, "Conformal Equivalence for Finitely Connected Regions", 71, [
        (1, "Analysis on a Finitely Connected Region", 71),
        (2, "Conformal Equivalence with an Analytic Jordan Region", 76),
        (3, "Boundary Values for a Conformal Equivalence Between "
            "Finitely Connected Jordan Regions", 81),
        (4, "Convergence of Univalent Functions", 85),
        (5, "Conformal Equivalence with a Circularly Slit Annulus", 90),
        (6, "Conformal Equivalence with a Circularly Slit Disk", 97),
        (7, "Conformal Equivalence with a Circular Region", 100),
    ]),
    (16, "Analytic Covering Maps", 109, [
        (1, "Results for Abstract Covering Spaces", 109),
        (2, "Analytic Covering Spaces", 113),
        (3, "The Modular Function", 116),
        (4, "Applications of the Modular Function", 123),
        (5, "The Existence of the Universal Analytic Covering Map", 125),
    ]),
    (17, "De Branges's Proof of the Bieberbach Conjecture", 133, [
        (1, "Subordination", 133),
        (2, "Loewner Chains", 136),
        (3, "Loewner's Differential Equation", 142),
        (4, "The Milin Conjecture", 148),
        (5, "Some Special Functions", 156),
        (6, "The Proof of de Branges's Theorem", 160),
    ]),
    (18, "Some Fundamental Concepts from Analysis", 169, [
        (1, "Bergman Spaces of Analytic and Harmonic Functions", 169),
        (2, "Partitions of Unity", 174),
        (3, "Convolution in Euclidean Space", 177),
        (4, "Distributions", 185),
        (5, "The Cauchy Transform", 192),
        (6, "An Application: Rational Approximation", 196),
        (7, "Fourier Series and Cesàro Sums", 198),
    ]),
    (19, "Harmonic Functions Redux", 205, [
        (1, "Harmonic Functions on the Disk", 205),
        (2, "Fatou's Theorem", 210),
        (3, "Semicontinuous Functions", 217),
        (4, "Subharmonic Functions", 220),
        (5, "The Logarithmic Potential", 229),
        (6, "An Application: Approximation by Harmonic Functions", 235),
        (7, "The Dirichlet Problem", 237),
        (8, "Harmonic Majorants", 245),
        (9, "The Green Function", 246),
        (10, "Regular Points for the Dirichlet Problem", 253),
        (11, "The Dirichlet Principle and Sobolev Spaces", 259),
    ]),
    (20, "Hardy Spaces on the Disk", 269, [
        (1, "Definitions and Elementary Properties", 269),
        (2, "The Nevanlinna Class", 272),
        (3, "Factorization of Functions in the Nevanlinna Class", 278),
        (4, "The Disk Algebra", 286),
        (5, "The Invariant Subspaces of H^p", 290),
        (6, "Szegő's Theorem", 295),
    ]),
    (21, "Potential Theory in the Plane", 301, [
        (1, "Harmonic Measure", 301),
        (2, "The Sweep of a Measure", 311),
        (3, "The Robin Constant", 313),
        (4, "The Green Potential", 315),
        (5, "Polar Sets", 320),
        (6, "More on Regular Points", 328),
        (7, "Logarithmic Capacity: Part 1", 331),
        (8, "Some Applications and Examples of Logarithmic Capacity", 339),
        (9, "Removable Singularities for Functions in the Bergman Space", 344),
        (10, "Logarithmic Capacity: Part 2", 352),
        (11, "The Transfinite Diameter and Logarithmic Capacity", 355),
        (12, "The Refinement of a Subharmonic Function", 360),
        (13, "The Fine Topology", 367),
        (14, "Wiener's criterion for Regular Points", 376),
    ]),
]

BACK = [
    ("References",      384),
    ("List of Symbols", 389),
    ("Index",           391),
]


def build_toc():
    """Return [(level, label, phys_page_1based, kind, key)] in book order."""
    out = [(lv, lab, ph, 'front', key) for lv, lab, ph, _k, key in FRONT]
    for cno, ctitle, cpage, secs in CH:
        out.append((1, "Chapter %d. %s" % (cno, ctitle), cpage + K,
                    'chap', (cno, ctitle)))
        for sno, stitle, spage in secs:
            out.append((2, "\u00a7%d. %s" % (sno, stitle), spage + K,
                        'sec', (cno, sno, stitle)))
        # exercises: appended by the writer if the heading is really there
    for btitle, bpage in BACK:
        out.append((1, btitle, bpage + K, 'back', btitle))
    return out


if __name__ == '__main__':
    t = build_toc()
    print("entries:", len(t))
    for e in t[:6]:
        print(e)
