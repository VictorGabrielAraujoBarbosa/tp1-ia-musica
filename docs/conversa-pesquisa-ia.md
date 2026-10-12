# Reactive Generative Music for Games

*Created: 10/7/2026, 8:47:23 PM*

---

**You**

i want to create generative music through generative means. i want to start with something simple, like bass n drums with some synths. the important thing is that i want the music to be reactive to the state of a game (maybe this means a markov chain would be better suited). this is for an assignment in a course im taking. my idea is the following: i'll simulate a racing game race (think something like need for speed). i will have 3 variables, racer you, racer opponent, and police. these go from 0 to 1, representing progression in the race track. rules built upon these variables are what i want to drive the music, to be the state for the state machine or the state for the markov chain. i want the beat to be odd when you are behind the other person, to cause a sensation of unease, and even when you're ahead, to cause a feeling of accomplishment. to introduce or stop instruments according to events like if the race is coming to a close or the police is closing in. the output of the project should be a midi. i want to create a simple html page to play the whole thing as an interface. by the way, the race sequence is pre-determined, like a recording, we'd store it in a convenient format, but the dynamic music system would sample the current variables from the recording every second or so and transition the beat accordingly. the implication of this is that the recording could be swapped with a real game with an interface and the dynamic music system should come to life. i need your help with scoping out the landscape for this. i dont need help with the webpage or the recording format, that can be sorted out later. what i need help with is figuring out what is the best generative music method for this? ideally, id fill it with midis that i composed (or derived from them) with lmms and a digital instrument (need your help to figure out which).

---

**Assistant**

# Scoping a state-reactive generative music system (bass, drums, synths, MIDI output)

**Recommendation:** Use Markov chains, with the transition probabilities conditioned on the race state and learned from loops you compose. Add a small rule layer on top for the on/off events. Also, the deadline is **09/10/2026 at 11:59 PM**, two days from now, so I've kept the scope to what fits in that time.

## 1. Fit with the assignment

- You must pick exactly one of grammars, GAs or Markov chains and use only that. You also have to state the order, justify it, say how the probabilities are obtained, and discuss the low-order vs high-order trade-off. The system must produce several different pieces from the same configuration, and you must vary at least one hyperparameter. The stylistic constraint goes in the abstract [^1].
- AI help is allowed for auxiliary code, but not for generating the whole method implementation or the abstract. Declare it in the README with links to the conversations [^1].
- Grad students get 3 pages and must cite at least 3 more papers. If you're a grad student, the related work below covers that.

**Why Markov rather than the other two:**
- A GA's fitness loop is a poor fit for a sample-every-second system.
- A probabilistic grammar is a real alternative. It suits odd meters well: a 7/8 bar can be 2+2+3, 3+2+2 or 2+3+2. But a grammar doesn't give you "learned from my own loops" for free.
- A Markov chain is cheap to sample in real time. You can also make its matrix a function of the state, which is the idea you already had.

**Prior work you can cite:**
- Prechtl built a generator whose parameters control the transition matrix of a Markov chord model and can be changed continuously in real time. Game tension drove the music, with more dissonance and a faster tempo as tension rose. In his evaluation the dynamic condition was rated and felt as the most tense and exciting [^2]. This is nearly your architecture.
- Plans & Morelli (experience-driven procedural music) survey Markov models, generative grammars and evolutionary algorithms for game music [^3]. Their transition work models viewpoints with Markov models to generate music between two composed pieces [^4].
- Ramanto et al. drive a Markov generator by mood, with per-mood tempo, pitch range, note values and chord dominance [^5].
- For drums specifically, CAMEL models Carnatic percussion with n-grams and Markov chains [^6]. `markovdrummer` builds a Markov chain from a MIDI drum groove and generates new beats [^7].
- A survey of generative music in games says it is not widely used because of resource demands and unpredictable output quality [^8]. That is a good argument for learning the chains from material you composed.

## 2. Suggested architecture

**State abstraction.** Don't feed raw floats into the music. Compute a few discrete or continuous features from the three variables:

| Feature | From | Used for |
|---|---|---|
| `gap = you − opp` | race | meter: ahead → even (4/4), behind → odd (7/8 or 5/4) |
| `police_dist = you − police` | race | tension and layer gating |
| `phase = max(you, opp)` | race | finale layers when near 1.0 |

These are my design choices, not findings. The tension from odd meters is a plausible hypothesis. A music-production source says odd meters like 5/4 and 7/8 create rhythmic tension because their beat groupings are less predictable than 4/4 [^9]. I didn't find a rigorous study of "odd meter → unease". Treat that as your assignment's hypothesis, and consider a short listening check with a few classmates.

**Two practical traps:**
- **Sample at bar boundaries.** Latch the state once per bar and apply changes only at the next bar line. A bar is about 2 s, so sampling every second means you'd be switching mid-bar. Add hysteresis (for example, switch to odd only after `gap < −0.03` for 2 bars) so the meter doesn't flicker when the lead is close.
- **A different meter means different step grids.** 4/4 has 16 sixteenth-note steps, 7/8 has 14, and 5/4 has 20. Train or keep a separate chain per meter (for example `drums_even`, `drums_odd`).

**Generative layer: one chain per instrument, matrix conditioned on state.**
- **Drums:** step-level tokens (the set of drum hits per step), order 2, in the style of `markovdrummer`.
- **Bass:** step-level or bar-level tokens (pitch or rest), order 1–2. Constrain it to the current root or scale.
- **Synth (arp, pad):** chord or arp-pattern tokens at bar level, order 1.
- **Conditioning:** keep one matrix per state: `calm`, `tense`, and for odd and even meters. Blend them as `P = (1−t)·P_calm + t·P_tense` with `t` from the police and finale features. Prechtl's continuous parameter control is the precedent [^2].

**Rule layer (vertical layering).** Gate the stems on and off with simple rules, which is a small state machine. Gating tracks is a standard adaptive technique called vertical remixing, next to horizontal resequencing [^10]. Example:
- police close → add a hi-hat or ostinato synth.
- last 10% of the race → add a lead and raise drum density.
- police far and you're ahead → pad only.

A caveat: "use exclusively one method" could be read strictly. I'd state in the abstract that the generation is entirely the Markov chain, and that the layering gates are a deterministic wrapper. Ask your professor if you're unsure.

**Order trade-off with a small corpus.** With only a handful of composed loops, an order-3+ chain over step tokens will mostly replay your loops verbatim. That's the memorization risk the assignment asks you to discuss. Use order 1–2 at step level, or order 1 at bar level, where the chain re-sequences your own bars (a stochastic form of horizontal resequencing).

**Hyperparameters to vary for the 3+ required pieces:** order (1 vs 2 vs 3), the blend `t`, temperature, the random seed, and the odd-meter choice.

## 3. Tools and instruments

**Pipeline:** Python generates the `.mid` file. `mido` is enough (it writes tracks, program changes and time-signature events) [^11]. `pretty_midi` or `music21` also work. Then render the audio with FluidSynth.

**Soundfont:** GeneralUser GS is GM/GS compatible, with 261 instrument presets and 13 drum kits [^12]. It's free to use for your own music, private or commercial [^13]. Using it keeps the browser demo and the offline audio the same.

**LMMS for composing the source loops:**
- Built-in instruments include TripleOscillator, Monstro, ZynAddSubFX, LB302 and SF2/GIG players [^14].
- A community tutorial describes strings and lead on Zyn with bass on TripleOsc [^15]. So:
  - **Bass:** Monstro or TripleOscillator (saw or square with a filter envelope), or LB302 for an acid-style bass.
  - **Synths:** ZynAddSubFX for pad and strings, Monstro for lead and arp.
  - **Drums:** the GM drum kit from the soundfont, or Kicker for a punchy kick.
- **Caveat on LMMS MIDI export.** A GitHub issue reports that MIDI export writes everything as piano, which leaves instruments wrong; it is closed and linked to PR #8048, with no fix details in what I read [^16]. LMMS has no bundled soundfont, and you can set a default one for loading MIDI files [^17]. For imported drum tracks, you may need to route the track to SF2 bank 128 by hand [^18].
- **Practical advice:** do a 10-minute test now. Compose a 1-bar loop in LMMS, export it, and open it in Python. If the notes survive, use LMMS for composition only. Pitch and timing are what matter for the corpus, since instruments are assigned by your own program-change and channel mapping. If the export is broken, write the seed loops straight into MIDI from Python, or use another MIDI editor for the corpus. The drums should go on channel 10 for GM.

## 4. Two-day plan

1. **Today:** compose 3–4 loops each for drums, bass and synth in 4/4 and 7/8 (calm and tense versions). Export them, parse them into step tokens, and train the chains.
2. **Today/tomorrow:** build the generator with a fixed fake race recording. Write a `state → (meter, t, layer mask)` function and sample at bar boundaries. Render at least 3 `.mid` files with different seeds and orders, then render them to audio.
3. **Tomorrow:** write the abstract, using the order trade-off and the hyperparameter table as results, then fill in the README, `requirements.txt` and the AI-use declaration. The webpage can wait.

If you tell me whether you're an undergrad or grad student and your preferred language, I can draft the abstract outline and the related-work paragraph.

**References**

[^1]: 8f40dcaff843-tp1_geracao_musical_simbolica_1 (36%)
[^2]: [Open Research Online](https://oro.open.ac.uk/45340/) (12%)
[^3]: [Experience-Driven Procedural Music Generation for Games](https://www.researchgate.net/publication/260583920_Experience-Driven_Procedural_Music_Generation_for_Games) (4%)
[^4]: [(PDF) Experience-Driven Procedural Music Generation for Games](https://www.academia.edu/91440779/Experience_Driven_Procedural_Music_Generation_for_Games) (5%)
[^5]: [Markov Chain Based Procedural Music Generator with ...](https://adada.info/journals/Vol.21_No.01-3.pdf) (5%)
[^6]: [(PDF) camel: carnatic percussion music generation using n-gram...](https://www.researchgate.net/publication/309359274_CAMEL_CARNATIC_PERCUSSION_MUSIC_GENERATION_USING_N-GRAM_MODELS) (2%)
[^7]: [GitHub - mapio/markovdrummer: An experiment in algorithmic generation of drum grooves. · GitHub](https://github.com/mapio/markovdrummer) (2%)
[^8]: [Generative Music in Video Games: State of the Art, Challenges, and Prospects](https://www.academia.edu/83151810/Generative_Music_in_Video_Games_State_of_the_Art_Challenges_and_Prospects) (8%)
[^9]: [Time signatures explained for modern music producers](https://acestudio.ai/blog/time-signatures-explained/) (5%)
[^10]: [Adaptive Music Composition for Games | Request PDF](https://www.researchgate.net/publication/334021077_Adaptive_Music_Composition_for_Games) (1%)
[^11]: [Standard MIDI Files — Mido 1.3.2 documentation](https://mido.readthedocs.io/en/stable/files/midi.html) (3%)
[^12]: [GeneralUser GS](https://www.schristiancollins.com/generaluser) (2%)
[^13]: [Search results for various | Musical Artifacts](https://musical-artifacts.com/artifacts?formats=7z&q=various) (2%)
[^14]: [Plugin System | LMMS/lmms | DeepWiki](https://deepwiki.com/LMMS/lmms/6-plugin-system) (1%)
[^15]: [Video Tutorials | English Stable (1.2.x) | User manual](https://docs.lmms.io/user-manual/en-1.2/resources/videos) (1%)
[^16]: [MIDI export exports everything as piano, making things out of tune · Issue #5287 · LMMS/lmms · GitHub](https://github.com/LMMS/lmms/issues/5287) (2%)
[^17]: [SF2 Player | User manual](https://docs.lmms.io/user-manual/instruments/sf2-player) (4%)
[^18]: [Import MIDI drums track - LMMS • Forums](https://lmms.io/forum/viewtopic.php?t=1059) (4%)

---

