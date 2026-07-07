import { describe, expect, it } from "vitest";
import type { GbdUlOut } from "./application-types";
import {
  distributeGbdUlResponse,
  gbdTargetAttr,
  isGbdLookupTrigger,
  isGbdPrefillTarget,
  looksLikeBin,
} from "./gbd-ul-prefill";

const gbdResponse: GbdUlOut = {
  bin: "123456789012",
  name: "ТОО «Пример»",
  oked: "62.01",
  oked_name: "Разработка ПО",
  address: "г. Астана, ул. Примерная, 1",
  director: "Иванов Иван Иванович",
  mock: true,
  disclaimer: "Имитация ГБД ЮЛ: тестовый справочник, а не реальный госреестр.",
};

describe("looksLikeBin", () => {
  it("accepts exactly 12 digits", () => {
    expect(looksLikeBin("123456789012")).toBe(true);
  });

  it("tolerates surrounding whitespace from paste", () => {
    expect(looksLikeBin("  123456789012 ")).toBe(true);
  });

  it("rejects a partially typed BIN", () => {
    expect(looksLikeBin("12345")).toBe(false);
  });

  it("rejects a non-numeric value", () => {
    expect(looksLikeBin("12345678901a")).toBe(false);
  });

  it("rejects non-string values", () => {
    expect(looksLikeBin(123456789012)).toBe(false);
    expect(looksLikeBin(null)).toBe(false);
    expect(looksLikeBin(undefined)).toBe(false);
  });
});

describe("isGbdLookupTrigger / isGbdPrefillTarget", () => {
  it("identifies the trigger field", () => {
    expect(isGbdLookupTrigger("gbd_ul.lookup")).toBe(true);
    expect(isGbdLookupTrigger("gbd_ul.name")).toBe(false);
    expect(isGbdLookupTrigger(null)).toBe(false);
  });

  it("identifies target fields and excludes the trigger itself", () => {
    expect(isGbdPrefillTarget("gbd_ul.name")).toBe(true);
    expect(isGbdPrefillTarget("gbd_ul.address")).toBe(true);
    expect(isGbdPrefillTarget("gbd_ul.lookup")).toBe(false);
    expect(isGbdPrefillTarget(null)).toBe(false);
    expect(isGbdPrefillTarget(undefined)).toBe(false);
  });
});

describe("gbdTargetAttr", () => {
  it("maps every documented target prefill to its GbdUlOut attribute", () => {
    expect(gbdTargetAttr("gbd_ul.name")).toBe("name");
    expect(gbdTargetAttr("gbd_ul.address")).toBe("address");
    expect(gbdTargetAttr("gbd_ul.oked")).toBe("oked");
    expect(gbdTargetAttr("gbd_ul.oked_name")).toBe("oked_name");
    expect(gbdTargetAttr("gbd_ul.director")).toBe("director");
  });

  it("returns null for the trigger and for unrelated prefill values", () => {
    expect(gbdTargetAttr("gbd_ul.lookup")).toBeNull();
    expect(gbdTargetAttr("other.thing")).toBeNull();
    expect(gbdTargetAttr(null)).toBeNull();
  });
});

describe("distributeGbdUlResponse", () => {
  it("fills every target field from the matching GbdUlOut attribute", () => {
    const fields = [
      { key: "applicant_bin", prefill: "gbd_ul.lookup" },
      { key: "company_name", prefill: "gbd_ul.name" },
      { key: "company_address", prefill: "gbd_ul.address" },
    ];
    expect(distributeGbdUlResponse(fields, gbdResponse)).toEqual({
      company_name: "ТОО «Пример»",
      company_address: "г. Астана, ул. Примерная, 1",
    });
  });

  it("ignores fields without a gbd_ul target prefill", () => {
    const fields = [
      { key: "unrelated", prefill: null },
      { key: "also_unrelated" },
    ];
    expect(distributeGbdUlResponse(fields, gbdResponse)).toEqual({});
  });
});
