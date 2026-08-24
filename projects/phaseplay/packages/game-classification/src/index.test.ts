import { describe, expect, it } from "vitest";
import { getGame, getGameEvidence, listGames, resolveAlias, searchGames } from ".";

describe("game catalog", () => {
  it("validates every seed at startup", () => expect(listGames()).toHaveLength(6));
  it("resolves punctuation-insensitive aliases", () => expect(resolveAlias("Huff N Xtra Puff")?.id).toBe("light-and-wonder:huff-n-x-tra-puff"));
  it("returns evidence separately", () => expect(getGameEvidence("aristocrat:buffalo-cash")[0]?.sourceType).toBe("manufacturer"));
  it("searches partial names", () => expect(searchGames("buffalo")).toHaveLength(3));
  it("keeps RTP attached to versions", () => expect(getGame("light-and-wonder:huff-n-even-more-puff-grand")?.versions.map((version) => version.rtpPercent)).toEqual([87, 96]));
});
