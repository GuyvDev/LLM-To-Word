declare namespace wasm_bindgen {
    /* tslint:disable */
    /* eslint-disable */

    export function capabilities_json(): string;

    export function convert_docx(markdown: string, source: string): Uint8Array;

    export function convert_html(markdown: string, source: string): string;

    export function detected_profile(source: string): string;

}
declare type InitInput = RequestInfo | URL | Response | BufferSource | WebAssembly.Module;

declare interface InitOutput {
    readonly memory: WebAssembly.Memory;
    readonly capabilities_json: () => [number, number];
    readonly convert_docx: (a: number, b: number, c: number, d: number) => [number, number, number, number];
    readonly convert_html: (a: number, b: number, c: number, d: number) => [number, number];
    readonly detected_profile: (a: number, b: number) => [number, number];
    readonly __wbindgen_externrefs: WebAssembly.Table;
    readonly __wbindgen_free: (a: number, b: number, c: number) => void;
    readonly __wbindgen_malloc: (a: number, b: number) => number;
    readonly __wbindgen_realloc: (a: number, b: number, c: number, d: number) => number;
    readonly __externref_table_dealloc: (a: number) => void;
    readonly __wbindgen_start: () => void;
}

/**
 * If `module_or_path` is {RequestInfo} or {URL}, makes a request and
 * for everything else, calls `WebAssembly.instantiate` directly.
 *
 * @param {{ module_or_path: InitInput | Promise<InitInput> }} module_or_path - Passing `InitInput` directly is deprecated.
 *
 * @returns {Promise<InitOutput>}
 */
declare function wasm_bindgen (module_or_path?: { module_or_path: InitInput | Promise<InitInput> } | InitInput | Promise<InitInput>): Promise<InitOutput>;
