import math
from copy import deepcopy
from sys import argv, exit

# How much to overlap child quads. E.g., if this value is 4, then the first
#  child node created will extend a quarter of the way past the midpoint.
EPSILON = 8.0
# How many points to allow in a leaf before it splits.
MAX = 25

# Represents one node in a quadtree.
class Node:
    def __init__(self, parent, x1, y1, x2, y2):
        self.parent = parent
        self.children = []
        self.points = []
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2


    # Returns whether or not a coordinate is contained by this node.
    def contains(self, x, y, epsilon = 0):
        return self.x1 - epsilon <= x <= self.x2 + epsilon \
               and self.y1 - epsilon <= y <= self.y2 + epsilon

    # Returns the area covered by this node.
    def area(self):
        return abs(self.x2 - self.x1) * abs(self.y2 - self.y1)

    # Returns the number of leaves at this node.
    def leaves(self):
        lvs = []

        to_check = [self]

        while to_check:
           cur = to_check.pop()

           if not cur.children:
               lvs.append(cur)
           else:
               for c in cur.children:
                   to_check.append(c)

        return lvs

    # Returns the area this node would be enlarged by to contain a point.
    def enlargement(self, x, y):
        return max(abs(self.x1 - x), abs(self.x2 - x)) \
               * max(abs(self.y1 - y), abs(self.y2 - y))

    # Enlarges a node such that it contains a point.
    def enlarge(self, x, y):
        if x < self.x1:
            # Expanding to the left.
            self.x1 = x
            if self.children:
                # Top left child expands left.
                self.children[0].enlarge(x, self.y1)
                # Bottom left child expands left.
                self.children[2].enlarge(x, self.y2)
        elif x > self.x2:
            # Expanding to the right.
            self.x2 = x
            if self.children:
                # Top right child expands right.
                self.children[1].enlarge(x, self.y1)
                # Bottom right child expands right.
                self.children[3].enlarge(x, self.y2)
        if y < self.y1:
            # Expanding up.
            self.y1 = y
            if self.children:
                # Top left child expands up.
                self.children[0].enlarge(self.x1, y)
                # Top right child expands up.
                self.children[1].enlarge(self.x2, y)
        elif y > self.y2:
            # Expanding down.
            self.y2 = y
            if self.children:
                # Bottom left child expands down.
                self.children[2].enlarge(self.x1, y)
                # Bottom right child expands down.
                self.children[3].enlarge(self.x2, y)

    # Adds a coordinate to this node and its children.
    def add(self, coord):
        if not self.children:
            self.points.append(coord)
        for child in self.children:
            if child.contains(coord[0], coord[1]):
                child.add(coord)
        if len(self.points) > MAX:
            self.split()

    # Splits this node into four.
    def split(self):
        # Create new leaves for the resulting four overlapping subdivisions.
        x_mid = (self.x2 - self.x1) / 2 + self.x1
        y_mid = (self.y2 - self.y1) / 2 + self.y1
        leaf1 = Node(self, self.x1, self.y1, x_mid + (self.x2 - x_mid) \
                     / EPSILON, y_mid + (self.y2 - y_mid) / EPSILON)
        leaf2 = Node(self, x_mid - (x_mid - self.x1) / EPSILON, self.y1, \
                     self.x2, y_mid + (self.y2 - y_mid) / EPSILON)
        leaf3 = Node(self, self.x1, y_mid - (y_mid - self.y1) / EPSILON, \
                     x_mid + (self.x2 - x_mid) / EPSILON, self.y2)
        leaf4 = Node(self, x_mid - (x_mid - self.x1) / EPSILON, y_mid \
                     - (y_mid - self.y1) / EPSILON, self.x2, self.y2)

        # Take all the points and add them to the containing new leaves.
        for point in self.points:
            if leaf1.contains(point[0], point[1]):
                leaf1.points.append(point)
            if leaf2.contains(point[0], point[1]):
                leaf2.points.append(point)
            if leaf3.contains(point[0], point[1]):
                leaf3.points.append(point)
            if leaf4.contains(point[0], point[1]):
                leaf4.points.append(point)

        # Add the new leaves as children of the current leaf.
        self.children = [leaf1, leaf2, leaf3, leaf4]
        # Clear the current leaf's point list.
        self.points = []        

    # Returns the JSON representation of this node and its children.
    def json(self):
        # Note that we don't need the parents for searching.
        return '{\n"x1": %f,\n"y1": %f,\n"x2": %f,\n"y2": %f,\n"children": [\n%s],\n"points": [\n%s\n]\n}\n' % (self.x1, self.y1, self.x2, self.y2, ', '.join([child.json() for child in self.children]), ', '.join(["[%f, %f, \"%s\", \"%s\"]" % (point[0], point[1], point[2], point[3]) for point in self.points]))

    # Returns bounding boxes in a format that Processing can draw.
    def __str__(self):
        return "rect(%f, %f, %f, %f);\n%s" % (self.y2, -self.x1, \
               -abs(self.y2 - self.y1), -abs(self.x2 - self.x1), \
               ''.join([str(child) for child in self.children]))

def main():
    # Start with an area larger than California to be safe.
    root = Node(None, 32.275814, -124.564671, 42.117975, -114.236181)

    if len(argv) != 5:
        print "Usage: python ca_q_tree.py <cities CSV> <lat> <long> <dist>\n" \
            + "   Where the CSV is formatted: name,lat; lon,email"
        exit()

    lat = float(argv[2])
    lon = float(argv[3])
    dist_n = float(argv[4])
    filename = argv[1]

    init_qtree(root, filename)
    distances = get_nearest_cities(root, lat, lon, dist_n)

    # Dump the quadtree to the JSON file.
    with open("json/%s_qtree.json" % \
        (filename[filename.rfind('/') + 1 : filename.rfind('.')]), "w") \
        as out_file:
        out_file.write(root.json())

    for d in distances:
       print d[2]
       print "%s, %s" % (d[0], d[1])

# initializes the quadtree using the given file name in csv format
def init_qtree_file(root, filename):
    with open(filename, "r") as city_file:
        # For every city in the file: 
        for line in city_file.readlines()[1:]:
            line = line.strip().split(",")
            coord = [float(n) for n in line[1].split(";")]
            coord.extend([line[0], line[2]])
           
            # If there is no tree, create a new one containing the city.
            if not root: 
                root = Node(None, coord[0], coord[1], coord[0], coord[1])
                root.points.append(coord)
            # Otherwise, add the city to the tree.
            else:
                root.enlarge(coord[0], coord[1])
                root.add(coord)

# initializes the quadtree using the given set of newspaper results
def init_qtree(root, results):
    for name, lat, lon, email in results:
        coord = [lat, lon, name, email]

        # If there is no tree, create a new one containing the city.
        if not root: 
            root = Node(None, lat, lon, lat, lon)
            root.points.append(coord)
        # Otherwise, add the city to the tree.
        else:
            root.enlarge(lat, lon)
            root.add(coord)

# returns all the newspapers of a quadtree rooted at a given state
# TODO - update this function to handle different states
def get_from_state(root):
    cities = []

    # iterate through each of the leaves
    for l in root.leaves():
        for p in l.points:
            cities.append(p)

    return cities

def get_nearest_cities(root, lat, lon, dist_n):
    key = [lat, lon]
    # Start with the root.
    to_check = [root]
    leaves = []
    cities = []

    while to_check:
        # Pop the next node to check from the stack. 
        cur_node = to_check.pop()
        # If it's not a leaf, append it to the list of leaves to check.
        if not cur_node.children:
            leaves.append(cur_node)
        # Otherwise, push all its children that contain the key onto the stack.    
        for child in cur_node.children:
            if child.contains(key[0], key[1]):
                to_check.append(child)

    if len(leaves) < 1:
       return cities

    if dist_n:
        return cities_within_distance(key,cities,leaves,dist_n)
    return nearest_city(key,leaves)

def cities_within_distance(key,cities,leaves,dist_n): 
    pt = leaves[0]

    # go out to the largest node containing the given radius
    while not pt.contains(key[0] + dist_n, key[1] + dist_n) \
        or not pt.contains(key[0] - dist_n, key[1] + dist_n) \
        or not pt.contains(key[0] + dist_n, key[1] - dist_n) \
        or not pt.contains(key[0] - dist_n, key[1] - dist_n):

        if pt.parent:
            pt = pt.parent
        else:
            break;

    # iterate through each of the leaves
    for l in pt.leaves():
        for p in l.points:
            dist = degrees_to_miles(math.fabs(p[0] - key[0]), \
                math.fabs(p[1] - key[1]))

            if dist < dist_n and p not in cities:
                cities.append(p)

    return cities

# Returns the number of miles, given latitude and longitude distances
def degrees_to_miles(dlat, dlon):
    delta = 69

    # Do some math here to handle longitude

    miles_lat = dlat * 69
    miles_lon = dlon * delta

    return math.sqrt(math.pow(miles_lon, 2) + math.pow(miles_lat, 2))

def nearest_city(key,leaves):
    city = []
    min_final = None
    dist_final = None
    # For each of the leaves that need to be linearly searched: 
    for cur_node in leaves:
        print "noFill();\nstroke(255,255,0);\nstrokeWeight(0.02);\n%s" \
              % str(cur_node)

        # Find the closest of the leaf's points to the key.
        min_point = cur_node.points[0]
        min_dist = math.sqrt(math.pow(min_point[0] - key[0], 2) \
                   + math.pow(min_point[1] - key[1], 2))
        for point in cur_node.points[1:]:
            dist = math.sqrt(math.pow(point[0] - key[0], 2) \
                   + math.pow(point[1] - key[1], 2))
            if dist < min_dist:
                min_dist = dist
                min_point = point
        # Update the final information if necessary.
        if min_final == None or min_dist < dist_final:
            dist_final = min_dist
            min_final = min_point

    city.append(min_final)
    return city 

if __name__ == "__main__":
    main()
