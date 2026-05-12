/**
 * engines/motion_canvas/src/utils/pattern_helper.ts
 * MaCode regex pattern factory — TypeScript version.
 *
 * Avoids Agents hand-writing 80+ character raw regexes.
 *
 * Usage:
 *   import {pattern} from '../utils/pattern_helper';
 *
 *   // Number patterns
 *   pattern.number.int();        // '[+-]?\\d+'
 *   pattern.number.float();      // '[+-]?(?:\\d+\\.?\\d*|\\.\\d+)(?:[eE][+-]?\\d+)?'
 *
 *   // Unit matching (number + space + unit)
 *   pattern.unit("m/s");         // '\\d+(?:\\.\\d+)?\\s*m/s'
 *
 *   // Composition
 *   const p = pattern.number.float() + pattern.string.whitespace() + pattern.unit("kg");
 *   pattern.match(p, "12.5 kg");
 */

// ------------------------------------------------------------------
// 1. Number patterns
// ------------------------------------------------------------------

class NumberPatterns {
  /** Signed integer. */
  int(): string {
    return String.raw`[+-]?\d+`;
  }

  /** Signed float (supports scientific notation). */
  float(): string {
    return String.raw`[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?`;
  }

  /** Hex integer (0x / 0X prefix). */
  hex(): string {
    return String.raw`0[xX][0-9a-fA-F]+`;
  }

  /** Percentage (e.g. 12.5%). */
  percent(): string {
    return String.raw`\d+(?:\.\d+)?%`;
  }
}

// ------------------------------------------------------------------
// 2. String patterns
// ------------------------------------------------------------------

class StringPatterns {
  /** Quoted string (no escape). */
  quoted(quote = '"'): string {
    return `${quote}[^${quote}]*${quote}`;
  }

  /** One or more whitespace characters. */
  whitespace(): string {
    return String.raw`\s+`;
  }
}

// ------------------------------------------------------------------
// 3. Time / file preset patterns
// ------------------------------------------------------------------

class TimePatterns {
  /** HH:MM:SS[.sss] time format. */
  hms(): string {
    return String.raw`\d{1,2}:\d{2}:\d{2}(?:\.\d+)?`;
  }

  /** Duration (e.g. 3.5s, 200ms, 2min). */
  duration(): string {
    return String.raw`\d+(?:\.\d+)?\s*(?:s|sec|seconds|ms|min|minutes)`;
  }
}

class FilePatterns {
  /** Common file path (defaults to py/mp4/png/csv/json). */
  path(exts: string[] = ['py', 'mp4', 'png', 'csv', 'json']): string {
    const extGroup = exts.join('|');
    return `[\\w\\-\\./]+\\.(?:${extGroup})`;
  }
}

// ------------------------------------------------------------------
// 4. Pattern factory facade
// ------------------------------------------------------------------

class PatternFactory {
  number = new NumberPatterns();
  string = new StringPatterns();
  time = new TimePatterns();
  file = new FilePatterns();

  /**
   * Generate `number + optional space + unit` matching pattern.
   *
   * @param u - Unit string, e.g. `"m/s"`, `"kg"`. Leave empty for generic unit placeholder.
   * @returns Pattern string ready for RegExp
   *
   * Example:
   *   pattern.unit("m/s")   // -> '\d+(?:\.\d+)?\s*m/s'
   *   pattern.unit("kg")    // -> '\d+(?:\.\d+)?\s*kg'
   */
  unit(u = '[a-zA-Z]+(?:/[a-zA-Z]+)?'): string {
    const escaped = u === '[a-zA-Z]+(?:/[a-zA-Z]+)?' ? u : u.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return String.raw`\d+(?:\.\d+)?\s*` + escaped;
  }

  /** Compile pattern string into RegExp. */
  compile(p: string, flags = ''): RegExp {
    return new RegExp(p, flags);
  }

  /** Match pattern p at the beginning of text. */
  match(p: string, text: string, flags = ''): RegExpMatchArray | null {
    return new RegExp(p, flags).exec(text);
  }

  /** Search for the first match of p in text. */
  search(p: string, text: string, flags = ''): RegExpMatchArray | null {
    return text.match(new RegExp(p, flags));
  }
}

/** Global singleton. */
export const pattern = new PatternFactory();
