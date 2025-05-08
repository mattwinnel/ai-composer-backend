\version "2.24.1"

\header {
  title = "Sunlight Through Dissonance 1A"
  composer = "Matt"
}

sopranoMelody = {
  \clef treble
  \key g \major
  \time 4/4

  g'2 a' | b'1 | c''2( a') | a'1 | b'1 |
  cis''2 d'' | d''1 | d''2( e'') | d''1 | e''2 f'' | f''1 |

  e''2( f'') | f''1 | g''2( a'') | b''1 |
  c'''2( b'') | b''1 | c'''1
}

verseLyrics = \lyricmode {
  Shine a -- cross the e -- ven -- ing sky,
  dreams a -- rise and fall.
}

trumpetOneMusic = {
  \clef treble
  \key g \major
  \time 4/4

  d'2 e' | d'1 | e'2( f') | fis'1 | g'1 |
  a'2 a' | a'1 | a'2( b') | bes'1 | c''2 c'' | c''1 |

  c''2( b') | b'1 | d''2 d'' | d''1 |
  g''2( fis'') | g''1 | e''1
}

trumpetTwoMusic = {
  \clef treble
  \key g \major
  \time 4/4

  b2 c' | b1 | a2( c') | d'1 | d'1 |
  e'2 f' | f1 | f2( g) | g1 | g2 a | a1 |

  a2( g) | g1 | b2 b | b1 |
  e'2( d') | d'1 | g'1
}

violaMusic = {
  \clef alto
  \key g \major
  \time 4/4

  g2 f | g1 | f2( d) | d1 | g1 |
  a2 d | d1 | d2( c) | e1 | a,2 a | d1 |

  a2( g) | g1 | g2 g | g1 |
  c2( d) | g1 | c1
}

pianoRight = {
  \clef treble
  \key g \major
  \time 4/4

  g'2 a' | b'1 | c''2( a') | a'1 | b'1 |
  cis''2 d'' | d''1 | d''2( e'') | d''1 | e''2 f'' | f''1 |

  e''2( f'') | f''1 | g''2( a'') | b''1 |
  c'''2( b'') | b''1 | c'''1
}

pianoLeft = {
  \clef bass
  \key g \major
  \time 4/4

  g2 f | g1 | f2( d) | d1 | g1 |
  a2 d | d1 | d2( c) | e1 | a,2 a | d1 |

  a2( g) | g1 | g2 g | g1 |
  c2( d) | g1 | c1
}

\score {
  <<
    \new Staff \with {
      instrumentName = "Soprano"
      shortInstrumentName = "Sop."
      midiInstrument = "voice oohs"
    } <<
      \new Voice = "soprano" { \sopranoMelody }
      \new Lyrics \lyricsto "soprano" { \verseLyrics }
    >>

    \new Staff \with {
      instrumentName = "Trumpet 1"
      shortInstrumentName = "Tpt. 1"
      midiInstrument = "trumpet"
    } { \trumpetOneMusic }

    \new Staff \with {
      instrumentName = "Trumpet 2"
      shortInstrumentName = "Tpt. 2"
      midiInstrument = "trumpet"
    } { \trumpetTwoMusic }

    \new Staff \with {
      instrumentName = "Viola"
      shortInstrumentName = "Vla."
      midiInstrument = "viola"
    } { \violaMusic }

    \new PianoStaff \with {
      instrumentName = "Piano"
      shortInstrumentName = "Pno."
    } <<
      \new Staff \with {
        midiInstrument = "acoustic grand"
      } { \pianoRight }

      \new Staff \with {
        midiInstrument = "acoustic grand"
      } { \pianoLeft }
    >>
  >>
  \layout { }
  \midi { }
}
\paper {
  left-margin = 25\mm
  right-margin = 15\mm
}
