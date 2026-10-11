import re
import xml.etree.ElementTree as ET

import grobidAltoStuff.altoStuff as altoStuff
import grobidAltoStuff.tryingDiff as tryingDiff

TEI = "{http://www.tei-c.org/ns/1.0}"


def _text_slots(element, skip_figures=False):
    if skip_figures and element.tag == TEI + "figure":
        return

    if element.tag.split("}")[-1] not in ("sub", "super"):
        if element.text:
            yield element, "text", element.text

        for child in list(element):
            yield from _text_slots(child, skip_figures)
            if child.tail:
                yield child, "tail", child.tail


def _insert_tags(owner, field, text, spans, parents):
    """Insert tags without losing text or existing XML elements."""
    parent = owner if field == "text" else parents[owner]
    insertion = (
        0 if field == "text"
        else list(parent).index(owner) + 1
    )

    setattr(owner, field, text[:spans[0][0]])

    for index, (start, end, kind) in enumerate(spans):
        tag = ET.Element(kind)
        tag.text = text[start:end]

        next_start = (
            spans[index + 1][0]
            if index + 1 < len(spans)
            else len(text)
        )
        tag.tail = text[end:next_start]
        parent.insert(insertion + index, tag)


def addScript(grobidpath, altopath, outputpath):
    tree = ET.parse(grobidpath)
    root = tree.getroot()

    parents = {
        child: parent
        for parent in root.iter()
        for child in parent
    }

    containers = root.findall(".//" + TEI + "abstract")
    containers += root.findall(
        "./" + TEI + "text/" + TEI + "body"
    )
    containers += root.findall(".//" + TEI + "figDesc")

    (
        altoStrings,
        altoWords,
        superFonts,
        subFonts,
    ) = altoStuff.AltoLists(altopath)

    # Match abstract, body, and each caption independently.
    for container in containers:
        slots = list(
            _text_slots(container, skip_figures=True)
        )

        words = []
        locations = []

        for slot_index, (_, _, text) in enumerate(slots):
            for match in re.finditer(r"\S+", text):
                words.append(match.group())
                locations.append(
                    (slot_index, match.start(), match.end())
                )

        supers, subs = matchStuff(
            words,
            altoStrings,
            altoWords,
            subFonts,
            superFonts,
        )

        changes = {}

        for kind, matches in [
            ("super", supers),
            ("sub", subs),
        ]:
            for word_index, _ in matches:
                slot_index, start, end = locations[word_index]
                changes.setdefault(slot_index, []).append(
                    (start, end, kind)
                )

        for slot_index, spans in changes.items():
            owner, field, text = slots[slot_index]
            _insert_tags(
                owner, field, text, sorted(spans), parents
            )

    tree.write(
        outputpath,
        encoding="utf-8",
        xml_declaration=True,
    )


def matchStuff(
    groStrings, altoStrings, altoWords, subFonts, superFonts
):
    matches = tryingDiff.getMatches(groStrings, altoStrings)

    supers = []
    subs = []

    for altDex, groDex, matchLen in matches:
        for i in range(matchLen):
            script = altoStuff.isScript(
                altoWords[altDex + i], superFonts, subFonts
            )

            if script == "super":
                supers.append(
                    [groDex + i, groStrings[groDex + i]]
                )
            elif script == "sub":
                subs.append(
                    [groDex + i, groStrings[groDex + i]]
                )

    return supers, subs
