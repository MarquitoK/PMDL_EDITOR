""" Function to generate a (not guaranteed optimal) triangle strip out
    of a set of triangles.

    Triangle strips can be required in geometry shaders or other
    applications.

    The performance and runtime of this solution is not optimal, but it is
    sufficient for small enough problems.

    Authors: Corbinian Gruber <dev.gruco0002@gmail.com>

    License: The Unlicence

        This is free and unencumbered software released into the public domain.

        Anyone is free to copy, modify, publish, use, compile, sell, or
        distribute this software, either in source code form or as a compiled
        binary, for any purpose, commercial or non-commercial, and by any
        means.

        In jurisdictions that recognize copyright laws, the author or authors
        of this software dedicate any and all copyright interest in the
        software to the public domain. We make this dedication for the benefit
        of the public at large and to the detriment of our heirs and
        successors. We intend this dedication to be an overt act of
        relinquishment in perpetuity of all present and future rights to this
        software under copyright law.

        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
        EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
        MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
        IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
        OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
        ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
        OTHER DEALINGS IN THE SOFTWARE.

        For more information, please refer to <https://unlicense.org>
"""


from collections import defaultdict

def build_edge_map(triangles):
    edge_map = defaultdict(list)

    for i, (a, b, c) in enumerate(triangles):
        edges = [
            tuple(sorted((a, b))),
            tuple(sorted((b, c))),
            tuple(sorted((c, a)))
        ]
        for e in edges:
            edge_map[e].append(i)

    return edge_map


def find_strip(triangles):
    triangles = [tuple(t) for t in triangles]
    edge_map = build_edge_map(triangles)

    used = [False] * len(triangles)
    result = []

    for start_idx in range(len(triangles)):
        if used[start_idx]:
            continue

        tri = triangles[start_idx]

        # iniciar strip
        strip = [tri[0], tri[1], tri[2]]
        used[start_idx] = True

        flip = False  # controla winding

        while True:
            if flip:
                edge = (strip[-1], strip[-2])
            else:
                edge = (strip[-2], strip[-1])

            edge_key = tuple(sorted(edge))
            candidates = edge_map[edge_key]

            found = False

            for idx in candidates:
                if used[idx]:
                    continue

                t = triangles[idx]
                s = set(t)

                if not s.issuperset(edge):
                    continue

                new_v = next(iter(s - set(edge)))

                # validar que realmente forma triángulo
                a, b = edge
                if len({a, b, new_v}) < 3:
                    continue  # degenerate real, evitar

                strip.append(new_v)
                used[idx] = True
                flip = not flip
                found = True
                break

            if not found:
                break

        # conectar strips con degenerates
        if not result:
            result.extend(strip)
        else:
            # degenerates: repetir último y primero
            result.append(result[-1])
            result.append(strip[0])
            result.extend(strip)

    return result
