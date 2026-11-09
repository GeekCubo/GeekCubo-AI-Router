// Vercel AI SDK + GeekCubo
//
//   npm install ai @ai-sdk/openai
//
// The @ai-sdk/openai provider lets you point at any OpenAI-compatible base URL.
// GeekCubo serves the OpenAI Chat Completions protocol, so this works as a drop-in.

import { createOpenAI } from "@ai-sdk/openai";
import { generateText, streamText } from "ai";

export const geekcubo = createOpenAI({
  baseURL: "http://127.0.0.1:8787/v1",
  apiKey: process.env.GEEKCUBO_API_KEY!, // sk-geek-...
});

// model="auto" → GeekCubo picks a capable model with your routing strategy
export async function ask(prompt: string) {
  const { text } = await generateText({
    model: geekcubo("auto"),
    prompt,
  });
  return text;
}

// Streaming
export async function ask_stream(prompt: string) {
  const { textStream } = await streamText({
    model: geekcubo("auto"),
    prompt,
  });
  for await (const chunk of textStream) process.stdout.write(chunk);
}

// Pin a specific model
export const haiku = geekcubo("claude-3-5-haiku-latest");
export const sonnet = geekcubo("claude-3-5-sonnet-latest");
export const gpt4o = geekcubo("gpt-4o");
