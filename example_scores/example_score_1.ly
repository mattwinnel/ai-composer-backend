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
  Light a path through sha -- dows deep,
  call.
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

drumSet = \drummode {
  \time 4/4
  hh8 hh hh hh hh hh hh hh |
  bd4 sn bd sn |
  hh8 hh sn hh hh hh sn hh |
  bd8 bd sn4 tomml8 tommh tomfh4 |
  hh8 hh hh hh hh hh hh hh |
  bd4 sn bd sn |
  hh8 hh sn hh hh hh sn hh |
  bd4 sn tomml8 tommh tomfh4 |
  hh4 hh hh hh |
  bd8 sn bd sn hh hh sn hh |
  hh8 hh hh hh hh hh hh hh |
  bd4 sn tomfh4 tomfh |
  hh8 sn hh sn hh sn hh sn |
  bd4 sn bd4 sn |
  tomml8 tommh tomfh4 tomfh |
  hh8 hh sn hh hh sn hh sn |
  bd4 sn hh8 hh hh hh hh hh |
  hh8 hh sn hh hh sn hh sn 
}

auxPerc = \drummode {
  tambourine8 tambourine tambourine tambourine tambourine tambourine tambourine tambourine |
  triangle4 r tambourine4 r |
  tambourine8 r tambourine r triangle r tambourine r |
  r4 r4 r4 r4 |
  tambourine4 triangle4 tambourine4 triangle4 |
  tambourine8 tambourine r tambourine triangle r tambourine r |
  r4 triangle4 tambourine4 r |
  tambourine8 tambourine tambourine tambourine triangle triangle r r |
  tambourine4 r triangle4 r |
  r8 r tambourine tambourine r r tambourine r |
  triangle4 triangle4 tambourine4 r |
  r4 r r tambourine8 tambourine |
  tambourine8 r triangle r tambourine r triangle r |
  triangle4 tambourine4 r2 |
  r8 tambourine tambourine tambourine triangle r tambourine r |
  r2 triangle4 tambourine4 |
  tambourine8 tambourine triangle triangle tambourine r tambourine r |
  r4 r r r
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

    \new DrumStaff \with {
      instrumentName = "Drum Set"
      shortInstrumentName = "Dr."
      drumStyleTable = #drums-style
      midiInstrument = "standard kit"
    } {
      \new DrumVoice { \drumSet }
    }

    \new DrumStaff \with {
      instrumentName = "Aux Perc"
      shortInstrumentName = "Aux"
      drumStyleTable = #percussion-style
      midiInstrument = "orchestral kit"
    } {
      \new DrumVoice { \auxPerc }
    }
  >>
  \layout { }
  \midi { }
}

\paper {
  left-margin = 25\mm
  right-margin = 15\mm
}
