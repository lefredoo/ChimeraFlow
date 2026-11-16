import type { Operator } from "./api-types";
import type { MessageKey } from "./i18n";

/** Message key of each rule operator (a symbol or a short word). */
export const OPERATOR_KEYS: Record<Operator, MessageKey> = {
  eq: "op.eq",
  ne: "op.ne",
  lt: "op.lt",
  lte: "op.lte",
  gt: "op.gt",
  gte: "op.gte",
  contains: "op.contains",
  in: "op.in",
};
