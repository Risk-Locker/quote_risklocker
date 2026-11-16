"use client";

import React from "react";
import { ReviewHeaderCard, type ReviewHeaderCardProps } from "./ReviewHeaderCard";

export type ReviewHeaderProps = ReviewHeaderCardProps;

export function ReviewHeader(props: ReviewHeaderProps) {
  return <ReviewHeaderCard {...props} />;
}
