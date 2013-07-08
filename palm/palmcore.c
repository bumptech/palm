/* TODO --
 *
 * scan for security..
 *
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <assert.h>
#include <string.h>

#include "palmcore.h"

void write_varint_value(unsigned char **ptr, uint64_t value) {
    unsigned char *chr = (unsigned char *)*ptr;
    while (1) {
        *chr = (value & 127);
        value = value >> 7;
        if (!value)
            break;
        *chr |= 128;
        chr++;
    }
    *ptr = chr + 1;
}

int read_varint_value(unsigned char **ptr, uint64_t *result, int *iters,
        unsigned char *limit) {
    unsigned char *chr = (unsigned char*)*ptr;
    uint64_t acc = 0;
    uint64_t x;
    for (x=0; x < 10; x++) {
        acc |= ((uint64_t)(*chr & 127)) << (7 * x);
        if (!(*chr & 128))
            break;
        chr++;
        if (chr == limit) return 0; // overflow
    }
    if (x == 10)
        return 0; // error reading varint.. too long!
    chr++;

    *ptr = (char *)chr;

    *result = acc;
    *iters = x;
    return 1;
}

static int pbf_ensure_space(pbf_protobuf *pbf, uint64_t max) {
    if (max > 100000)
        return 0; // refuse to allocate this much ram

    int mark = pbf->num_marks;
    pbf_mark * cur;
    pbf->num_marks = max + 100;
    pbf->marks = realloc(pbf->marks, sizeof(pbf_mark) * pbf->num_marks);

    for (; mark < pbf->num_marks; mark++) {
        cur = &pbf->marks[mark];
        cur->exists = 0;
        cur->last = NULL; // sentinel.. no last on initial (no repeated)
        cur->next = NULL;
        cur->repeats = NULL;
        cur->repeated_alloc = 0;
        cur->repeated_used = 0;
    }

    return 1;
}

int pbf_exists(pbf_protobuf *pbf, uint64_t field_num) {
    if (field_num < 0 || field_num > pbf->max_mark)
        return 0;
    return pbf->marks[field_num].exists;
}

void pbf_remove(pbf_protobuf *pbf, uint64_t field_num) {
    if (field_num < 0 || field_num > pbf->max_mark)
        return;

    pbf->marks[field_num].exists = 0;
    pbf->marks[field_num].last = NULL;
    pbf->marks[field_num].repeated_used = 0;
}

void pbf_add_slab(pbf_mark *head) {
    /* Create/grow repeated allocation */
    int i;
    pbf_mark *cur;
    if (head->repeated_alloc == 0) {
        head->repeated_alloc = REPEATED_START_SIZE;
    } else {
        head->repeated_alloc *= 2;
    }

    assert(head->repeated_alloc <= REPEATED_HARD_CAP);
    head->repeats = (pbf_mark *)realloc(head->repeats, head->repeated_alloc * sizeof(pbf_mark));

    // start at _new_ records
    for (i = 0; i < head->repeated_alloc; i++) {
        cur = head->repeats + i;
        cur->next = head->repeats + (i + 1);
        if (i >= head->repeated_used)
            cur->exists = 0;
    }
    cur->next = NULL;
    head->next = head->repeats;
}

static inline pbf_mark * pbf_get_mark_for_write(pbf_protobuf *pbf,
    uint64_t field_num, uint64_t field_type, pbf_mark **rhead) {
    pbf_mark *cur, *head;
    int success;

    if (field_num <= 0)
        return NULL;

    if (field_num >= pbf->num_marks) {
        success = pbf_ensure_space(pbf, field_num);
        if (!success) return NULL; // cannot handle high field numbers with design
    }

    if (field_num > pbf->max_mark)
        pbf->max_mark = field_num;

    head = &pbf->marks[field_num];
    cur = head->last ? head->last : head;
    if (cur->exists) {
        if (head->repeated_used == head->repeated_alloc) {
            pbf_add_slab(head);
        }
        cur = head->repeats + head->repeated_used;
        head->repeated_used++;
        head->last = cur;
    }
    cur->exists = 1;
    cur->ftype = field_type;

    *rhead = head;

    return cur;
}

static void pbf_scan (pbf_protobuf *pbf, char* stringmap, int maxstringid) {
    uint64_t key;
    int success, iters;
    uint64_t field_num;
    uint64_t field_type;
    unsigned char *ptr = pbf->data;
    pbf->parsed = 0;
    unsigned char *limit = pbf->data + pbf->data_length;
    pbf_mark *cur, *head;
    while (ptr < limit) {
        char *start = ptr;
        success = read_varint_value(&ptr, &key, &iters, limit);
        if (!success) return;


        field_num = key >> 3;
        field_type = key & 7;

        // validate things that should be bytestrings are indeed, and vice-versa
        if (field_num > 0 && field_num <= maxstringid &&
                ((field_type == pbf_type_length && !stringmap[field_num]) ||
                 (field_type != pbf_type_length && stringmap[field_num])))
            return;

        //printf("%lu\n", field_num);
        cur = pbf_get_mark_for_write(pbf, field_num, field_type, &head);
        if (!cur) return; // something failed in alloc etc

        cur->raw = start;
        cur->buf_len = 0;


        switch (field_type) {
            case pbf_type_varint:
                if (!read_varint_value(&ptr, &cur->fdata.i64, &iters, limit)) return;
                break;
            case pbf_type_length:
                if (!read_varint_value(&ptr, &cur->fdata.s.len, &iters, limit)) return;
                cur->fdata.s.data = ptr;
                ptr += cur->fdata.s.len;
                break;
            case pbf_type_fixed64:
                if (limit - ptr < 8) return;
                cur->fdata.i64 = *(uint64_t*)ptr;
                ptr += sizeof(uint64_t);
                break;
            case pbf_type_fixed32:
                if (limit - ptr < 4) return;
                cur->fdata.i32 = *(uint32_t*)ptr;
                ptr += sizeof(uint32_t);
                break;
            default: // unknown type
                return;
        }
        if (ptr > limit)
            return; // overflow on string length, etc
        cur->raw_len = ptr - cur->raw;
    }
    pbf->parsed = 1;
}

unsigned char *pbf_serialize(pbf_protobuf *pbf, int *length) {
    register int x;

    uint32_t size = 0;
    pbf_mark *mark, *head;
    /* XXX protect against giant allocations? */

    /* maximum size needed? */
    uint32_t *fields = malloc((pbf->max_mark + 1) * sizeof(uint32_t));
    uint32_t *cf = fields;
    for(x=1; x <= pbf->max_mark; x++) {
        head = mark = &pbf->marks[x];
        if (mark->exists) {
            *cf = x;
            cf++;
            while (1) {
                size += mark->raw_len + mark->buf_len;
                if (!head->last || mark == head->last) break;
                mark = mark->next;
            }
        }
    }
    *cf = 0;

    unsigned char *out = (char *)malloc(size);

    unsigned char *ptr = out;

    for(cf=fields; *cf != 0; cf++) {
        head = mark = &pbf->marks[*cf];
        if (head->exists) {
            while (1) {
                if (mark->buf_len) {
                    memcpy(ptr, mark->buf, mark->buf_len);
                    ptr += mark->buf_len;
                }
                if (mark->raw_len) {
                    memcpy(ptr, mark->raw, mark->raw_len);
                    ptr += mark->raw_len;
                }
                if (!head->last || mark == head->last) break;
                mark = mark->next;
            }
        }
    }

    *length = ptr - out;
    free(fields);
    return out;
}

pbf_protobuf * pbf_load(char *data, uint64_t size, char *stringmap, uint64_t maxstringid) {
    pbf_protobuf *pbf = (pbf_protobuf *)malloc(sizeof(pbf_protobuf));

    pbf->data = (unsigned char *)data; // assumed.. retention on behalf of caller
    pbf->data_length = size; // assumed.. retention on behalf of caller
    pbf->num_marks = 0;
    pbf->max_mark = 0;
    pbf->marks = NULL;

    pbf_scan(pbf, stringmap, maxstringid);

    if (!pbf->parsed) {
        pbf_free(pbf);
        return NULL;
    }

    return pbf;
}

void pbf_free(pbf_protobuf *pbf) {
    int i;
    pbf_mark *cur;

    /* free repeated slabs */
    for (i=1; i <= pbf->max_mark; i++) {
        cur = &pbf->marks[i];
        if (cur->repeats)
            free(cur->repeats);
    }

    if (pbf->marks)
        free(pbf->marks);
    free(pbf);
}

static inline pbf_mark * pbf_get_field_mark(pbf_protobuf *pbf, 
        uint64_t field_num,
        int last) {
    
    if (field_num <= 0 || field_num > pbf->max_mark)
        return NULL;

    pbf_mark *cur = &pbf->marks[field_num];
    if (!cur->exists)
        return NULL;

    return (last && cur->last) ? cur->last : cur;
}

/***********************************************************************
 * GET BYTES */

static inline void pbf_raw_get_bytes(pbf_mark *cur,
        char **out, uint64_t *length) {

    *out = cur->fdata.s.data;
    *length = cur->fdata.s.len;
}

int pbf_get_bytes(pbf_protobuf *pbf, uint64_t field_num,
        char **out, uint64_t *length) {
    pbf_mark *cur = pbf_get_field_mark(pbf, field_num, 1);
    if (!cur) return 0;

    pbf_raw_get_bytes(cur, out, length);

    return 1;
}

int pbf_get_bytes_stream(pbf_protobuf *pbf, uint64_t field_num,
        pbf_byte_stream_callback cb, void *passthrough) {
    pbf_mark *head;
    pbf_mark *cur = pbf_get_field_mark(pbf, field_num, 0);
    if (!cur) return 0;

    head = cur;
    char *v;
    uint64_t length;

    while (1) {
        pbf_raw_get_bytes(cur, &v, &length);
        cb(v, length, passthrough);
        if (!head->last || cur == head->last) break;
        cur = cur->next;
    }

    return 1;
}

/*********************************************************************************
 * GET UNSIGNED INTEGER, DOUBLE, FLOAT, ETC */
static inline pbf_get_raw_integer(pbf_mark *cur, uint64_t *res) {
    switch (cur->ftype) {
        case pbf_type_fixed32:
            *res = cur->fdata.i32;
            break;
        default:
            *res = cur->fdata.i64;
            break;
    }
}

int pbf_get_integer(pbf_protobuf *pbf, uint64_t field_num, uint64_t *res) {
    pbf_mark *cur = pbf_get_field_mark(pbf, field_num, 1);
    if (!cur) return 0;

    pbf_get_raw_integer(cur, res);
    return 1;
}

int pbf_get_integer_stream(pbf_protobuf *pbf, uint64_t field_num, 
        pbf_uint_stream_callback cb, void *passthrough) {
    pbf_mark *head;
    pbf_mark *cur = pbf_get_field_mark(pbf, field_num, 0);
    if (!cur) return 0;
    head = cur;
    uint64_t v;

    while (1) {
        pbf_get_raw_integer(cur, &v);
        cb(v, passthrough);
        if (!head->last || cur == head->last) break;
        cur = cur->next;
    }
}


/*********************************************************************************
 * GET SIGNED INTEGERS */
static inline int pbf_get_raw_signed_integer(pbf_mark *cur, int64_t *res,
        int32_t *res32, int use_zigzag) {

    int is_32 = res32 != NULL ? 1 : 0;
    switch (cur->ftype) {
        case pbf_type_fixed32:
            assert(is_32);
            assert(!use_zigzag);
            *res32 = cur->fdata.i32;
            break;
        default:
            if (!use_zigzag) {
                if (is_32) {
                    *res32 = (int32_t)cur->fdata.i64;
                }
                else
                    *res = cur->fdata.i64;
            }
            else {
                int64_t t = !(cur->fdata.i64 & 0x1) ? 
                            cur->fdata.i64 >> 1 : 
                            (cur->fdata.i64 >> 1) ^ (~0);

                if (is_32) 
                    *res32 = t;
                else 
                    *res = t;
            }
            break;
    }
}

int pbf_get_signed_integer(pbf_protobuf *pbf,
        uint64_t field_num, int64_t *res,
        int32_t *res32, int use_zigzag) {
    pbf_mark *cur = pbf_get_field_mark(pbf, field_num, 1);
    if (!cur) return 0;

    pbf_get_raw_signed_integer(cur, res, res32, use_zigzag);
    return 1;
}

int pbf_get_signed_integer_stream(pbf_protobuf *pbf,
        uint64_t field_num, int use_32, int use_zigzag,
        pbf_sint_stream_callback cb, void *passthrough) {
    pbf_mark *head;
    pbf_mark *cur = pbf_get_field_mark(pbf, field_num, 0);
    if (!cur) return 0;
    head = cur;
    
    int64_t i64, *p64;
    int32_t i32, *p32;

    if (use_32) {
        p64 = NULL;
        p32 = &i32;
    }
    else {
        p64 = &i64;
        p32 = NULL;
    }

    while (1) {
        pbf_get_raw_signed_integer(cur, p64, p32, use_zigzag);
        cb(i64, i32, passthrough);
        if (!head->last || cur == head->last) break;
        cur = cur->next;
    }

    return 1;
}

/* SET FUNCTIONS */
int pbf_set_bytes(pbf_protobuf *pbf, uint64_t field_num,
        char *out, uint64_t length) {
    int resized;
    pbf_mark *head;
    pbf_mark *cur = pbf_get_mark_for_write(
            pbf, field_num, pbf_type_length, &head);
    if (!cur) return 0;
    (void)head;

    cur->fdata.s.data = cur->raw = out;
    cur->fdata.s.len = cur->raw_len = length;
    unsigned char *ptr = cur->buf;
    write_varint_value(&ptr, field_num << 3 | pbf_type_length);
    write_varint_value(&ptr, length);
    cur->buf_len = ptr - cur->buf;

    return 1;
}

int pbf_set_integer(pbf_protobuf *pbf, uint64_t field_num,
        uint64_t value, int fixed) {
    pbf_mark *head;
    pbf_mark *cur = pbf_get_mark_for_write(
            pbf, field_num, 
            fixed == 0 ? pbf_type_varint :
            fixed == 32 ? pbf_type_fixed32 : 
            pbf_type_fixed64, &head);
    if (!cur) return 0;

    cur->raw_len = 0;
    cur->fdata.i64 = value;

    unsigned char *ptr = cur->buf;
    if (!fixed) {
        write_varint_value(&ptr, field_num << 3 | pbf_type_varint);
        write_varint_value(&ptr, value);
    }
    else if (fixed == 32){
        write_varint_value(&ptr, field_num << 3 | pbf_type_fixed32);
        *((uint32_t *)ptr) = (uint32_t)value;
        ptr += 4;
    }
    else if (fixed == 64){
        write_varint_value(&ptr, field_num << 3 | pbf_type_fixed64);
        *((uint64_t *)ptr) = (uint64_t)value;
        ptr += 8;
    }
    else
        assert(0); // bad internal API call

    cur->buf_len = ptr - cur->buf;

    return 1;
}

/* XXX proper sfixed32 support? */
int pbf_set_signed_integer(pbf_protobuf *pbf, uint64_t field_num,
        int64_t value, int zigzag) {
    pbf_mark *head;
    pbf_mark *cur = pbf_get_mark_for_write(
            pbf, field_num, pbf_type_varint, &head);
    if (!cur) return 0;

    cur->raw_len = 0;

    unsigned char *ptr = cur->buf;

    write_varint_value(&ptr, field_num << 3 | pbf_type_varint);
    if (!zigzag) {
        cur->fdata.i64 = (uint64_t)value;
        write_varint_value(&ptr, (uint64_t)value);
    }
    else {
        uint64_t encoded = (value << 1) ^ (value >> 63);
        cur->fdata.i64 = encoded;
        write_varint_value(&ptr, encoded);
    }

    cur->buf_len = ptr - cur->buf;

    return 1;
}
